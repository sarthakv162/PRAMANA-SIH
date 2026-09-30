"""Normalises a stored response payload (any of AnswerCard/RefusalCard/ClassifyResult/
PatentRisk/AbsResult/TkRadar, as stored by `audit/receipts.py::build_receipt`) into one shape
every format renderer (`pdf.py`, `docx.py`, `md.py`) can walk without re-deriving per-type
layout logic three times (§6.11).

This module never re-runs the pipeline and never invents content: everything in a
`DossierItem` comes verbatim from the stored payload (already server-materialised evidence
text, §2) or from the receipt metadata passed in alongside it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.audit.receipts import StoredResult

DISCLAIMER = "Informational, not legal advice."


@dataclass
class QuoteBlock:
    citation_label: str
    page: int | None
    text: str


@dataclass
class DossierItem:
    request_id: str
    receipt_id: str
    entry_hash: str
    kind: str
    title: str
    corpus_version: str | None
    as_of: str | None
    jurisdiction: str | None
    summary_lines: list[str] = field(default_factory=list)
    quotes: list[QuoteBlock] = field(default_factory=list)
    note: str | None = None


_TITLES = {
    "answer": "Answer",
    "refusal": "Refusal",
    "result": "Classification result",
    "patent_risk": "Patent risk indicator",
    "abs": "ABS obligations checklist",
    "tk_radar": "TK radar",
}


def _quotes_from_evidence(evidence: dict[str, Any]) -> list[QuoteBlock]:
    return [
        QuoteBlock(
            citation_label=span.get("citation_label", span.get("section_key", ev_id)),
            page=span.get("page"),
            text=span.get("text", ""),
        )
        for ev_id, span in evidence.items()
    ]


def _answer_summary(payload: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for section in payload.get("sections", []):
        lines.append(f"{section.get('heading', section.get('jurisdiction', ''))}:")
        for claim in section.get("claims", []):
            lines.append(f"  [{claim.get('status')}] {claim.get('text')}")
        for gap in section.get("gaps", []):
            lines.append(f"  [gap] {gap.get('text')}")
    if payload.get("dropped_claims"):
        lines.append(f"{payload['dropped_claims']} statement(s) removed: could not be verified.")
    confidence = payload.get("confidence") or {}
    if confidence:
        lines.append(f"Confidence: {confidence.get('level')} ({confidence.get('score')})")
    return lines


def _refusal_summary(payload: dict[str, Any]) -> list[str]:
    return [f"Reason: {payload.get('reason')}", payload.get("message", "")]


def _classify_summary(payload: dict[str, Any]) -> list[str]:
    lines = [f"Category: {payload.get('category_label')}"]
    for req in payload.get("requirements", []):
        lines.append(f"  Requirement: {req.get('text')}")
    for name, item in (payload.get("ip_posture") or {}).items():
        lines.append(f"  IP posture — {name}: {item.get('risk')} — {item.get('note')}")
    abs_posture = payload.get("abs_posture") or {}
    if abs_posture:
        lines.append(f"  ABS posture: {abs_posture.get('summary')}")
    return lines


def _patent_risk_summary(payload: dict[str, Any]) -> list[str]:
    lines = [f"Overall risk indicator: {payload.get('gauge')} (score {payload.get('score')})"]
    for section in payload.get("per_section", []):
        lines.append(f"  s.{section.get('section')}: {section.get('risk')}")
        for reason in section.get("reasons", []):
            lines.append(f"    - {reason}")
    for help_item in payload.get("what_would_help", []):
        lines.append(f"  What would help: {help_item.get('text')}")
    return lines


def _abs_summary(payload: dict[str, Any]) -> list[str]:
    lines = [payload.get("summary", "")]
    for item in payload.get("checklist", []):
        status = "required" if item.get("required") else ("exempt" if item.get("exempt") else "n/a")
        lines.append(f"  [{status}] {item.get('title')} (authority: {item.get('authority')})")
        lines.append(f"    {item.get('detail')}")
    return lines


def _tk_radar_summary(payload: dict[str, Any]) -> list[str]:
    lines = ["Normalised ingredients:"]
    for ing in payload.get("normalized_ingredients", []):
        lines.append(f"  {ing.get('input')} -> {ing.get('canonical_latin')}")
    lines.append("Closest classical matches:")
    for match in payload.get("matches", []):
        lines.append(f"  {match.get('name')} (similarity {match.get('similarity')})")
    tkdl = payload.get("tkdl_query") or {}
    if tkdl:
        lines.append(f"TKDL query pack: {tkdl.get('text')}")
    for hit in payload.get("watchlist_hits", []):
        lines.append(f"Watchlist: {hit.get('case')} — {hit.get('outcome')}")
    return lines


_SUMMARY_BUILDERS = {
    "answer": _answer_summary,
    "refusal": _refusal_summary,
    "result": _classify_summary,
    "patent_risk": _patent_risk_summary,
    "abs": _abs_summary,
    "tk_radar": _tk_radar_summary,
}


def build_dossier_item(stored: StoredResult) -> DossierItem:
    payload = stored.result
    kind = payload.get("type", "unknown")
    evidence = payload.get("evidence") or {}
    quotes = _quotes_from_evidence(evidence) if isinstance(evidence, dict) else []
    if kind == "refusal":
        quotes = [
            QuoteBlock(
                citation_label=span.get("citation_label", ""),
                page=span.get("page"),
                text=span.get("text", ""),
            )
            for span in payload.get("nearest_sources", [])
        ]
    summary_builder = _SUMMARY_BUILDERS.get(kind)
    summary_lines = summary_builder(payload) if summary_builder else [str(payload)]

    return DossierItem(
        request_id=stored.request_id,
        receipt_id=stored.receipt_id,
        entry_hash=stored.entry_hash,
        kind=kind,
        title=_TITLES.get(kind, kind),
        corpus_version=payload.get("corpus_version"),
        as_of=str(payload.get("as_of")) if payload.get("as_of") else None,
        jurisdiction=payload.get("jurisdiction"),
        summary_lines=summary_lines,
        quotes=quotes,
    )


def missing_item(request_id: str) -> DossierItem:
    """Placeholder for a requested `request_id` with no stored result (expired, never
    existed, or from before this pipeline recorded results) — the dossier still lists it
    rather than silently dropping it, so the case file and the document agree on item count.
    """
    return DossierItem(
        request_id=request_id,
        receipt_id="",
        entry_hash="",
        kind="missing",
        title="Item not found",
        corpus_version=None,
        as_of=None,
        jurisdiction=None,
        note=f"No stored result for request_id={request_id!r}.",
    )
