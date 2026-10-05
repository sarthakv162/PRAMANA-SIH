"""GET /v1/corpus/versions — feeds the as-of UI's version picker. See §5.3."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

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
    rows = session.execute(sa.select(corpus_versions).order_by(corpus_versions.c.created_at.desc())).all()
    return [CorpusVersionInfo(label=r.label, status=r.status, created_at=r.created_at) for r in rows]


@router.get("/corpus/coverage")
def source_coverage(session: Session = Depends(get_session)) -> dict[str, Any]:
    import json
    from pathlib import Path

    import yaml

    from app.retrieval.repo import documents_for_version, live_corpus_version

    root = Path(__file__).resolve().parents[3]
    version = live_corpus_version(session)
    indexed = {d.short_key for d in documents_for_version(session, version[0])} if version else set()
    topics = yaml.safe_load((root / "corpus/coverage.yaml").read_text())["topics"]
    for topic in topics:
        topic["indexed_sources"] = [s for s in topic["sources"] if s in indexed]
        topic["missing_sources"] = [s for s in topic["sources"] if s not in indexed]
        topic["status"] = (
            "query_pack_only"
            if topic["id"] == "tkdl"
            else (
                "indexed"
                if topic["sources"] and not topic["missing_sources"]
                else "partial"
                if topic["indexed_sources"]
                else "not_indexed"
            )
        )
    report = root / "corpus/raw/source-check-latest.json"
    return {
        "corpus_version": version[1] if version else None,
        "topics": topics,
        "source_check": json.loads(report.read_text()) if report.exists() else None,
    }
