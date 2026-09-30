"""§6.7 verify: NLI entailment + regex guards decide each claim's status, or drop it.

Premise = the concatenation of *only* the claim's cited evidence spans — nothing else, so a
claim can't be "verified" against text it didn't actually cite.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config import get_settings
from app.generation.resolve import ResolvedClaim
from app.schemas.claims import Claim, ClaimChecks
from app.schemas.enums import ClaimStatus
from app.schemas.evidence import EvidenceSpan
from app.verification.guards import (
    dates_ok,
    modal_strength_matches,
    negation_ok,
    numbers_ok,
    section_refs_ok,
)
from app.verification.nli import entailment_score


@dataclass
class VerificationOutcome:
    claims: list[Claim]
    dropped_count: int
    mean_entailment: float  # over surviving claims; 0.0 if none survived


def _build_premise(evidence_ids: list[str], evidence_by_id: dict[str, EvidenceSpan]) -> str:
    return " ".join(evidence_by_id[eid].text for eid in evidence_ids)


def verify_claim(
    claim_id: str, resolved: ResolvedClaim, evidence_by_id: dict[str, EvidenceSpan]
) -> Claim | None:
    settings = get_settings()
    premise = _build_premise(resolved.evidence_ids, evidence_by_id)
    hypothesis = resolved.statement

    nli = entailment_score(premise, hypothesis)
    if nli.entailment < settings.nli_tau_low:
        return None

    # Numbers/dates/section-references: a mismatch here means the claim asserts something
    # the cited text doesn't actually say — drop outright, don't just downgrade (§6.7).
    if not (numbers_ok(hypothesis, premise) and dates_ok(hypothesis, premise)):
        return None
    if not section_refs_ok(hypothesis, premise):
        return None

    status = (
        ClaimStatus.VERIFIED if nli.entailment >= settings.nli_tau_high else ClaimStatus.PARTIAL
    )

    # Negation/modality: a hedge the claim drops, or a shall/may mismatch, downgrades
    # rather than drops (§6.7) — the claim is directionally right but overstates certainty.
    negation_passes = negation_ok(hypothesis, premise)
    modal_passes = modal_strength_matches(hypothesis, premise)
    if not (negation_passes and modal_passes):
        status = ClaimStatus.PARTIAL

    return Claim(
        id=claim_id,
        text=hypothesis,
        status=status,
        evidence_ids=resolved.evidence_ids,
        checks=ClaimChecks(
            nli_entail=nli.entailment,
            numbers_ok=True,
            dates_ok=True,
            negation_ok=negation_passes and modal_passes,
        ),
    )


def verify_claims(
    resolved_claims: list[ResolvedClaim], evidence_by_id: dict[str, EvidenceSpan]
) -> VerificationOutcome:
    claims: list[Claim] = []
    entailments: list[float] = []
    dropped = 0

    for i, resolved in enumerate(resolved_claims, start=1):
        claim = verify_claim(f"c{i}", resolved, evidence_by_id)
        if claim is None:
            dropped += 1
            continue
        claims.append(claim)
        entailments.append(claim.checks.nli_entail)

    mean_entail = sum(entailments) / len(entailments) if entailments else 0.0
    return VerificationOutcome(claims=claims, dropped_count=dropped, mean_entailment=mean_entail)
