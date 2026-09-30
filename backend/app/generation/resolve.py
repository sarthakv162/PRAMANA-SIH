"""§6.6 resolve step: map the model's `[E#]` references to real evidence IDs, drop anything
that cites an ID outside the pack or mixes jurisdictions. This is the boundary where model
output stops being trusted at face value — from here on, everything about a claim's
evidence is looked up from the pack the server built, never taken from the model's words.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.generation.claim_schema import GenerationResult, RawClaim
from app.retrieval.evidence_pack import NumberedSpan

_E_REF = re.compile(r"^E(\d+)$", re.IGNORECASE)


@dataclass
class ResolvedClaim:
    statement: str
    evidence_ids: list[str]  # real ev_xxxx IDs
    jurisdiction: str
    kind: str


@dataclass
class ResolveOutcome:
    resolved: list[ResolvedClaim]
    gaps: list[str]
    needs_clarification: str | None
    dropped: list[str]  # human-readable reasons, for logging/debugging only


def _lookup(numbered: list[NumberedSpan], ref: str) -> NumberedSpan | None:
    match = _E_REF.match(ref.strip())
    if not match:
        return None
    number = int(match.group(1))
    for item in numbered:
        if item.number == number:
            return item
    return None


def resolve_generation(
    generation: GenerationResult, numbered: list[NumberedSpan]
) -> ResolveOutcome:
    resolved: list[ResolvedClaim] = []
    dropped: list[str] = []

    for raw in generation.claims:
        outcome = _resolve_one(raw, numbered)
        if isinstance(outcome, str):
            dropped.append(outcome)
        else:
            resolved.append(outcome)

    return ResolveOutcome(
        resolved=resolved,
        gaps=list(generation.gaps),
        needs_clarification=generation.needs_clarification,
        dropped=dropped,
    )


def _resolve_one(raw: RawClaim, numbered: list[NumberedSpan]) -> ResolvedClaim | str:
    spans = []
    for ref in raw.evidence_ids:
        span = _lookup(numbered, ref)
        if span is None:
            return f"claim cites {ref!r}, not in the evidence pack — dropped"
        spans.append(span)

    jurisdictions = {s.span.jurisdiction for s in spans}
    if len(jurisdictions) > 1:
        return f"claim mixes jurisdictions {jurisdictions} — dropped (§2 jurisdiction firewall)"

    return ResolvedClaim(
        statement=raw.statement,
        evidence_ids=[s.evidence_id for s in spans],
        jurisdiction=jurisdictions.pop(),
        kind=raw.kind,
    )
