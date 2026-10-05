"""§6.4 `verify` + §6.7: NLI + guards decide each claim's status; confidence decides
abstain/review. No model call here beyond NLI — nothing about the claim's *wording* is
re-generated, only checked.
"""

from __future__ import annotations

from app.core.logging import get_logger
from app.intake.translate import back_translation_ok, translate_from_english
from app.orchestrator.state import RequestState
from app.schemas.enums import ClaimStatus
from app.schemas.evidence import EvidenceSpan
from app.verification.confidence import ConfidenceOutcome, compute_confidence
from app.verification.verify import verify_claims

logger = get_logger("orchestrator.verify")


def run(state: RequestState) -> ConfidenceOutcome:
    evidence_by_id: dict[str, EvidenceSpan] = {item.evidence_id: item.span for item in state.evidence_pack}
    outcome = verify_claims(state.resolved_claims, evidence_by_id)
    state.verification_feedback = (
        "The previous draft failed server verification: " + str(outcome.drop_reasons) if outcome.dropped_count else ""
    )
    state.verified_claims = outcome.claims
    state.dropped_claims = outcome.dropped_count
    state.mean_entailment = outcome.mean_entailment

    if state.lang.value != "en" and outcome.claims:
        translated_claims = []
        roundtrip_results = []
        for claim in outcome.claims:
            translated_text = translate_from_english(claim.text, state.lang)
            translation_ok = back_translation_ok(claim.text, translated_text, state.lang)
            roundtrip_results.append(translation_ok)
            translated_claims.append(
                claim.model_copy(
                    update={"text": translated_text, "status": claim.status if translation_ok else ClaimStatus.PARTIAL}
                )
            )
        state.verified_claims = translated_claims
        state.gaps = [translate_from_english(gap, state.lang) for gap in state.gaps]
        state.back_translation_ok = all(roundtrip_results)

    verified_ratio = (
        sum(c.status == ClaimStatus.VERIFIED for c in state.verified_claims) / len(state.resolved_claims)
        if state.resolved_claims
        else 0.0
    )
    confidence = compute_confidence(
        retrieval_margin=state.retrieval_margin,
        mean_entailment=outcome.mean_entailment,
        verified_ratio=verified_ratio,
        back_translation_ok=state.back_translation_ok,
    )
    if any(c.status == ClaimStatus.PARTIAL for c in state.verified_claims):
        confidence.review_recommended = True
    # Keep query text and generated claim text out of logs while making abstentions
    # diagnosable: the component signals reveal whether verification or calibration failed.
    logger.info(
        "request %s verification: resolved=%d verified=%d dropped=%d "
        "retrieval_margin=%.3f mean_entailment=%.3f verified_ratio=%.3f "
        "confidence=%.3f abstain=%s drop_reasons=%s",
        state.request_id,
        len(state.resolved_claims),
        len(outcome.claims),
        outcome.dropped_count,
        state.retrieval_margin,
        outcome.mean_entailment,
        verified_ratio,
        confidence.score,
        confidence.abstain,
        outcome.drop_reasons,
    )
    return confidence
