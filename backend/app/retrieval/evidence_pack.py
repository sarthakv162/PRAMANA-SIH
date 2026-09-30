"""Build the Evidence Pack (§6.4 `resolve`): materialise verbatim `EvidenceSpan` objects from
chunk rows, number them `E1…En` for the generation prompt, and assign stable `ev_` IDs.

This is the only place `EvidenceSpan.text` is produced. It is always `row.text` — the exact
substring stored at ingest time — never anything the LLM wrote (§2 design rule).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.core.hashing import sha256_hex
from app.retrieval import repo
from app.schemas.evidence import EvidenceSpan, Highlight

_CLAUSE_RE = re.compile(r"#s(.+)$")


def _clause_suffix(section_key: str) -> str | None:
    match = _CLAUSE_RE.search(section_key)
    return match.group(1) if match else None


def _citation_label(doc_title: str, section_key: str, heading: str | None) -> str:
    clause = _clause_suffix(section_key)
    if clause:
        return f"{doc_title} — s.{clause}"
    if heading:
        return f"{doc_title} — {heading}"
    return doc_title


def stable_evidence_id(chunk_id: str, char_start: int, char_end: int) -> str:
    """`ev_<12 hex chars>` — deterministic across requests for the same chunk/span, so the
    same citation always resolves to the same ID (useful for caching and for tests).
    """
    digest = sha256_hex(f"{chunk_id}:{char_start}:{char_end}")
    return f"ev_{digest[:12]}"


@dataclass
class NumberedSpan:
    """One `[E{n}]` line handed to the generation prompt (§6.6)."""

    number: int
    evidence_id: str
    chunk_id: str
    span: EvidenceSpan


def build_evidence_pack(
    session: Session,
    chunk_rows: list[sa.Row[Any]],
    corpus_version_label: str,
) -> list[NumberedSpan]:
    """Turn ranked chunk rows into numbered, citable `EvidenceSpan`s.

    Rows are expected to already be jurisdiction/as-of filtered (i.e. come from
    `retrieval/repo.py`); this function does no additional filtering, only materialisation.
    """
    if not chunk_rows:
        return []

    section_ids = list({str(row.section_id) for row in chunk_rows})
    sections_by_id = {str(s.id): s for s in repo.fetch_sections_by_ids(session, section_ids)}

    document_ids = list({str(s.document_id) for s in sections_by_id.values()})
    documents_by_id = {
        str(d.id): d for d in (repo.fetch_document(session, doc_id) for doc_id in document_ids) if d
    }

    numbered: list[NumberedSpan] = []
    for i, row in enumerate(chunk_rows, start=1):
        section = sections_by_id.get(str(row.section_id))
        document = documents_by_id.get(str(section.document_id)) if section else None
        if section is None or document is None:
            continue

        evidence_id = stable_evidence_id(str(row.id), row.char_start, row.char_end)
        highlights = [Highlight(**h) for h in (row.bboxes or [])] if row.bboxes else []

        span = EvidenceSpan(
            id=evidence_id,
            doc_id=document.short_key,
            doc_title=document.title,
            doc_type=row.doc_type,
            jurisdiction=row.jurisdiction,
            citation_label=_citation_label(document.title, section.section_key, section.heading),
            section_key=section.section_key,
            section_path=list(section.path or []),
            page=row.page or section.page_start or 0,
            page_end=row.page or section.page_end or row.page or 0,
            char_start=row.char_start,
            char_end=row.char_end,
            text=row.text,
            sha256=row.sha256,
            effective_from=row.effective_from,
            effective_to=row.effective_to,
            corpus_version=corpus_version_label,
            source_url=document.source_url,
            pdf_url=f"/v1/documents/{document.short_key}/pdf",
            highlights=highlights,
        )
        numbered.append(
            NumberedSpan(number=i, evidence_id=evidence_id, chunk_id=str(row.id), span=span)
        )
    return numbered


def render_prompt_spans(numbered: list[NumberedSpan]) -> str:
    """`[E1] <citation_label>\\n<text>` blocks, per §6.6 — what the LLM actually reads."""
    lines = []
    for item in numbered:
        lines.append(f"[E{item.number}] {item.span.citation_label}\n{item.span.text}")
    return "\n\n".join(lines)
