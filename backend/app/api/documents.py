"""GET /v1/documents, GET /v1/documents/{doc_id}/pdf, GET /v1/spans/{evidence_id}. See §5.3.

MOCK_MODE=1 synthesises DocumentSummary rows from the EvidenceSpan pool embedded in the answer
fixtures (there's no dedicated documents fixture in §5.6) and serves span lookups the same way.
Real corpus browsing lands with ingestion (M1).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.db import get_session
from app.core.errors import ApiError
from app.core.fixtures import load_fixture
from app.retrieval import repo
from app.retrieval.evidence_pack import build_evidence_pack, stable_evidence_id
from app.retrieval.repo import documents, live_corpus_version
from app.schemas.documents import DocumentSummary
from app.schemas.enums import Jurisdiction
from app.schemas.evidence import EvidenceSpan

router = APIRouter(tags=["documents"])
CORPUS_ROOT = Path(__file__).resolve().parents[3] / "corpus"


def _mock_evidence_pool() -> dict[str, dict[str, Any]]:
    pool: dict[str, dict[str, Any]] = {}
    for fixture_name in ("answer_card_in.json", "answer_card_both_hi.json"):
        pool.update(load_fixture(fixture_name).get("evidence", {}))
    return pool


def _mock_documents() -> list[DocumentSummary]:
    seen: dict[str, DocumentSummary] = {}
    for span in _mock_evidence_pool().values():
        if span["doc_id"] in seen:
            continue
        effective_to = span.get("effective_to")
        seen[span["doc_id"]] = DocumentSummary(
            id=span["doc_id"],
            short_key=span["doc_id"],
            title=span["doc_title"],
            doc_type=span["doc_type"],
            jurisdiction=span["jurisdiction"],
            issuer=None,
            source_url=span["source_url"],
            language="en",
            in_force_from=date.fromisoformat(span["effective_from"]),
            in_force_to=date.fromisoformat(effective_to) if effective_to else None,
        )
    return list(seen.values())


@router.get("/documents", response_model=list[DocumentSummary])
async def list_documents(
    jurisdiction: Jurisdiction | None = None,
    doc_type: str | None = None,
    session: Session = Depends(get_session),
) -> list[DocumentSummary]:
    settings = get_settings()
    if settings.mock_mode:
        docs = _mock_documents()
    else:
        rows = session.execute(sa.select(documents)).all()
        docs = [
            DocumentSummary(
                id=row.short_key,
                short_key=row.short_key,
                title=row.title,
                doc_type=row.doc_type,
                jurisdiction=row.jurisdiction,
                issuer=row.issuer,
                source_url=row.source_url,
                language=row.language,
                in_force_from=row.in_force_from,
                in_force_to=row.in_force_to,
            )
            for row in rows
        ]
    if jurisdiction is not None:
        docs = [d for d in docs if d.jurisdiction == jurisdiction]
    if doc_type is not None:
        docs = [d for d in docs if d.doc_type == doc_type]
    return docs


@router.get("/documents/{doc_id}/pdf")
async def get_document_pdf(doc_id: str, session: Session = Depends(get_session)) -> Response:
    settings = get_settings()
    if settings.mock_mode:
        if doc_id not in {d.id for d in _mock_documents()}:
            raise HTTPException(status_code=404, detail="document not found")
        raise ApiError(
            code="pdf_unavailable", message="No PDF in mock mode.", status_code=501
        )

    document = repo.fetch_document_by_short_key(session, doc_id)
    if document is None:
        raise HTTPException(status_code=404, detail="document not found")
    pdf_path = CORPUS_ROOT / document.pdf_path
    if not pdf_path.exists():
        raise ApiError(code="pdf_unavailable", message="PDF file missing on disk.", status_code=404)
    return FileResponse(pdf_path, media_type="application/pdf")


@router.get("/spans/{evidence_id}", response_model=EvidenceSpan)
async def get_span(evidence_id: str, session: Session = Depends(get_session)) -> EvidenceSpan:
    settings = get_settings()
    if settings.mock_mode:
        pool = _mock_evidence_pool()
        if evidence_id not in pool:
            raise HTTPException(status_code=404, detail="evidence span not found")
        return EvidenceSpan.model_validate(pool[evidence_id])

    version = live_corpus_version(session)
    if version is None:
        raise HTTPException(status_code=404, detail="no live corpus_version")
    corpus_version_id, corpus_version_label = version
    chunk_row = repo.find_chunk_by_evidence_id(
        session, corpus_version_id, stable_evidence_id, evidence_id
    )
    if chunk_row is None:
        raise HTTPException(status_code=404, detail="evidence span not found")

    pack = build_evidence_pack(session, [chunk_row], corpus_version_label)
    return pack[0].span
