"""§6.7 verify: NLI entailment + regex guards decide each claim's status, or drop it.

The verifier uses only model-cited spans plus their exact parent-section spans from the
retrieved evidence pack; any added parent span is also attached to the returned claim.
"""

from __future__ import annotations

import re
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
    drop_reasons: dict[str, int]


def _build_premise(evidence_ids: list[str], evidence_by_id: dict[str, EvidenceSpan]) -> str:
    # Document identity and locators are server-owned source context. Without them,
    # an otherwise supported claim naming the Act or clause can look unsupported.
    return "\n".join(
        f"{evidence_by_id[eid].citation_label} [{evidence_by_id[eid].jurisdiction}]\n"
        f"{' > '.join(evidence_by_id[eid].section_path)}\n{evidence_by_id[eid].text}"
        for eid in evidence_ids
    )


def _with_parent_context(evidence_ids: list[str], evidence_by_id: dict[str, EvidenceSpan]) -> list[str]:
    """Attach available parent-section spans to clause citations for checking and display.

    This remains a citation-preserving proof: added spans must be in the retrieved evidence
    pack, belong to the same document/jurisdiction/version, and have a section path that is
    an exact ancestor of the model-cited span.
    """
    contextualized: list[str] = []
    for evidence_id in evidence_ids:
        span = evidence_by_id[evidence_id]
        parents = [
            candidate
            for candidate in evidence_by_id.values()
            if candidate.doc_id == span.doc_id
            and candidate.jurisdiction == span.jurisdiction
            and candidate.corpus_version == span.corpus_version
            and candidate.section_key != span.section_key
            and candidate.section_path
            and len(candidate.section_path) < len(span.section_path)
            and span.section_path[: len(candidate.section_path)] == candidate.section_path
        ]
        parents.sort(key=lambda candidate: len(candidate.section_path))
        for parent in parents:
            if parent.id not in contextualized:
                contextualized.append(parent.id)
        if evidence_id not in contextualized:
            contextualized.append(evidence_id)
    return contextualized


def _cited_section_refs(evidence_ids: list[str], evidence_by_id: dict[str, EvidenceSpan]) -> set[str]:
    """Return section references proven by the server-owned evidence locators.

    Ingested clause keys use forms such as ``document#s3(p)`` and nested forms such as
    ``document#s25(3)(a)``. The citation can support each containing section locator even
    when the verbatim excerpt begins after the heading.
    """
    refs: set[str] = set()
    for evidence_id in evidence_ids:
        section_key = evidence_by_id[evidence_id].section_key
        marker = section_key.rsplit("#s", maxsplit=1)
        if len(marker) != 2:
            continue
        match = re.match(r"\d+[A-Za-z]*(?:\([A-Za-z0-9]+\))*", marker[1])
        if match is None:
            continue
        section_number = re.match(r"\d+[A-Za-z]*", match.group())
        if section_number is None:
            continue
        reference = section_number.group()
        refs.add(f"section {reference}")
        for child in re.findall(r"\(([A-Za-z0-9]+)\)", match.group()):
            reference += f"({child})"
            refs.add(f"section {reference}")
    return refs


def verify_claim(claim_id: str, resolved: ResolvedClaim, evidence_by_id: dict[str, EvidenceSpan]) -> Claim | None:
    return _verify_claim_with_reason(claim_id, resolved, evidence_by_id)[0]


def _verify_claim_with_reason(
    claim_id: str, resolved: ResolvedClaim, evidence_by_id: dict[str, EvidenceSpan]
) -> tuple[Claim | None, str | None]:
    settings = get_settings()
    cited_evidence_ids = _with_parent_context(resolved.evidence_ids, evidence_by_id)
    premise = _build_premise(cited_evidence_ids, evidence_by_id)
    citation_metadata = "\n".join(evidence_by_id[evidence_id].citation_label for evidence_id in cited_evidence_ids)
    hypothesis = resolved.statement

    nli = entailment_score(premise, hypothesis)
    if nli.entailment < settings.nli_tau_low:
        return None, "nli_below_threshold"

    # Numbers/dates/section-references: a mismatch here means the claim asserts something
    # the cited text doesn't actually say — drop outright, don't just downgrade (§6.7).
    if not numbers_ok(hypothesis, premise, citation_metadata):
        return None, "unsupported_number"
    if not dates_ok(hypothesis, premise, citation_metadata):
        return None, "unsupported_date"
    citation_refs = _cited_section_refs(cited_evidence_ids, evidence_by_id)
    if not section_refs_ok(hypothesis, premise, citation_refs):
        return None, "unsupported_section_reference"

    status = ClaimStatus.VERIFIED if nli.entailment >= settings.nli_tau_high else ClaimStatus.PARTIAL

    # Negation/modality: a hedge the claim drops, or a shall/may mismatch, downgrades
    # rather than drops (§6.7) — the claim is directionally right but overstates certainty.
    negation_passes = negation_ok(hypothesis, premise)
    modal_passes = modal_strength_matches(hypothesis, premise)
    if not (negation_passes and modal_passes):
        status = ClaimStatus.PARTIAL

    return (
        Claim(
            id=claim_id,
            text=hypothesis,
            status=status,
            evidence_ids=cited_evidence_ids,
            checks=ClaimChecks(
                nli_entail=nli.entailment,
                numbers_ok=True,
                dates_ok=True,
                negation_ok=negation_passes and modal_passes,
            ),
        ),
        None,
    )


def verify_claims(resolved_claims: list[ResolvedClaim], evidence_by_id: dict[str, EvidenceSpan]) -> VerificationOutcome:
    claims: list[Claim] = []
    entailments: list[float] = []
    dropped = 0
    drop_reasons: dict[str, int] = {}

    for i, resolved in enumerate(resolved_claims, start=1):
        claim, reason = _verify_claim_with_reason(f"c{i}", resolved, evidence_by_id)
        if claim is None:
            dropped += 1
            if reason:
                drop_reasons[reason] = drop_reasons.get(reason, 0) + 1
            continue
        claims.append(claim)
        entailments.append(claim.checks.nli_entail)

    mean_entail = sum(entailments) / len(entailments) if entailments else 0.0
    return VerificationOutcome(
        claims=claims,
        dropped_count=dropped,
        mean_entailment=mean_entail,
        drop_reasons=drop_reasons,
    )
