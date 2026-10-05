"""GET /v1/health — always real, works regardless of MOCK_MODE."""

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import answer_model_id, embedding_model_id, get_settings
from app.core.db import get_session
from app.retrieval.repo import embedding_model_for_version, live_corpus_version
from app.schemas.health import HealthStatus, ModelsStatus

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthStatus)
async def health(session: Session = Depends(get_session)) -> HealthStatus:
    settings = get_settings()
    version = None
    available = set()
    if not settings.mock_mode and settings.inference_runtime == "transformers":
        from app.generation.transformers_runtime import ready

        if ready():
            available = {answer_model_id(settings), embedding_model_id(settings)}
    elif not settings.mock_mode:
        try:
            async with httpx.AsyncClient(timeout=2) as client:
                response = await client.get(settings.ollama_base_url + "/api/tags")
                response.raise_for_status()
                available = {m["name"] for m in response.json()["models"]}
        except (httpx.HTTPError, KeyError, ValueError):
            pass
    if settings.mock_mode:
        corpus_version = "2026.09.28-a"
    else:
        try:
            version = live_corpus_version(session)
            corpus_version = version[1] if version else "none"
        except Exception:
            corpus_version = "unknown"
    from app.verification.nli import _model_and_tokenizer

    return HealthStatus(
        status="ok"
        if settings.mock_mode
        or (version and answer_model_id(settings) in available and embedding_model_id(settings) in available)
        else "degraded",
        mock_mode=settings.mock_mode,
        public_demo_mode=settings.public_demo_mode,
        inference_runtime=settings.inference_runtime,
        storage_mode=settings.storage_mode,
        query_transport=settings.query_transport,
        corpus_version=corpus_version,
        corpus_embedding_compatible=bool(
            version and embedding_model_for_version(session, version[0]) == embedding_model_id(settings)
        ),
        models=ModelsStatus(
            llm=answer_model_id(settings),
            embed=embedding_model_id(settings),
            nli=settings.nli_model,
            llm_ready=answer_model_id(settings) in available,
            embed_ready=embedding_model_id(settings) in available,
            nli_ready=bool(_model_and_tokenizer.cache_info().currsize),
        ),
    )
