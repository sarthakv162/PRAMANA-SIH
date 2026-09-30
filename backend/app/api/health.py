"""GET /v1/health — always real, works regardless of MOCK_MODE."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.db import get_session
from app.retrieval.repo import live_corpus_version
from app.schemas.health import HealthStatus, ModelsStatus

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthStatus)
async def health(session: Session = Depends(get_session)) -> HealthStatus:
    settings = get_settings()
    if settings.mock_mode:
        corpus_version = "2026.09.28-a"
    else:
        try:
            version = live_corpus_version(session)
            corpus_version = version[1] if version else "none"
        except Exception:
            corpus_version = "unknown"
    return HealthStatus(
        status="ok",
        corpus_version=corpus_version,
        models=ModelsStatus(
            llm=settings.llm_model,
            embed=settings.embed_model,
            nli=settings.nli_model,
        ),
    )
