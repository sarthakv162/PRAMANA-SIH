"""GET /v1/corpus/versions — feeds the as-of UI's version picker. See §5.3."""

from __future__ import annotations

from datetime import UTC, datetime

import sqlalchemy as sa
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.db import get_session
from app.retrieval.repo import corpus_versions
from app.schemas.documents import CorpusVersionInfo
from app.schemas.enums import CorpusVersionStatus

router = APIRouter(tags=["corpus"])


@router.get("/corpus/versions", response_model=list[CorpusVersionInfo])
async def list_corpus_versions(session: Session = Depends(get_session)) -> list[CorpusVersionInfo]:
    settings = get_settings()
    if settings.mock_mode:
        return [
            CorpusVersionInfo(
                label="2026.09.28-a",
                status=CorpusVersionStatus.LIVE,
                created_at=datetime(2026, 9, 28, tzinfo=UTC),
            )
        ]
    rows = session.execute(
        sa.select(corpus_versions).order_by(corpus_versions.c.created_at.desc())
    ).all()
    return [
        CorpusVersionInfo(label=r.label, status=r.status, created_at=r.created_at) for r in rows
    ]
