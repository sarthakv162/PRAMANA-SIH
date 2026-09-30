"""§6.4 `verify` + §6.7: NLI + guards decide each claim's status; confidence decides
abstain/review. No model call here beyond NLI — nothing about the claim's *wording* is
re-generated, only checked.
"""

from __future__ import annotations

from app.orchestrator.state import RequestState
from app.schemas.evidence import EvidenceSpan
from app.verification.confidence import ConfidenceOutcome, compute_confidence
from app.verification.verify import verify_claims


def run(state: RequestState) -> ConfidenceOutcome:
    evidence_by_id: dict[str, EvidenceSpan] = {
        item.evidence_id: item.span for item in state.evidence_pack
    }
    outcome = verify_claims(state.resolved_claims, evidence_by_id)
    state.verified_claims = outcome.claims
    state.dropped_claims = outcome.dropped_count
    state.mean_entailment = outcome.mean_entailment

    verified_ratio = (
        len(outcome.claims) / len(state.resolved_claims) if state.resolved_claims else 0.0
    )
    return compute_confidence(
        retrieval_margin=state.retrieval_margin,
        mean_entailment=outcome.mean_entailment,
        verified_ratio=verified_ratio,
        back_translation_ok=state.back_translation_ok,
    )
