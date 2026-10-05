"""PRAMANA backend entrypoint. Base path /v1 for every route (§5)."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from app.api import abs as abs_api
from app.api import (
    classify,
    conversations,
    corpus,
    documents,
    dossier,
    escalations,
    health,
    patent_risk,
    query,
    receipts,
    speech,
    tk,
)
from app.api import eval as eval_api
from app.config import get_settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging, get_logger
from app.core.rate_limit import RateLimiter

configure_logging()
logger = get_logger("startup")


def _warm_live_models() -> None:
    """Load the local models before accepting live requests, outside their 45s budget."""
    from app.verification.nli import _model_and_tokenizer as nli_model

    nli_model()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    if not get_settings().mock_mode:
        logger.info("Loading the local citation verification model for live mode.")
        await run_in_threadpool(_warm_live_models)
        logger.info("Live models are ready.")

    async def purge_history() -> None:
        from app.core.db import SessionLocal
        from app.history.service import purge_expired

        def clean() -> None:
            with SessionLocal() as session:
                purge_expired(session)

        while True:
            try:
                await run_in_threadpool(clean)
            except Exception:
                logger.error("History expiry cleanup failed; expired content remains excluded from reads.")
            await asyncio.sleep(3600)

    task = asyncio.create_task(purge_history()) if not get_settings().mock_mode else None
    try:
        yield
    finally:
        if task:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task


app = FastAPI(
    title="PRAMANA",
    description="Proof-carrying, multilingual assistant for Ayurvedic IP, ABS and "
    "drug-regulatory questions. Informational, not legal advice.",
    version="0.1.0",
    lifespan=lifespan,
)

_rate_limiter = RateLimiter(
    requests=get_settings().rate_limit_requests,
    window_s=get_settings().rate_limit_window_s,
)


@app.middleware("http")
async def enforce_ip_rate_limit(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    # Do not trust X-Forwarded-For unless a trusted proxy is explicitly configured.
    identity = request.client.host if request.client else "unknown"
    allowed, retry_after = _rate_limiter.allow(identity)
    if not allowed:
        return JSONResponse(
            status_code=429,
            headers={"Retry-After": str(retry_after)},
            content={
                "error": {
                    "code": "rate_limited",
                    "message": "Too many requests. Please retry shortly.",
                    "request_id": request.headers.get("x-request-id", "req_unknown"),
                }
            },
        )
    response = await call_next(request)
    response.headers.setdefault("X-RateLimit-Limit", str(_rate_limiter.requests))
    return response


register_error_handlers(app)

API_ROUTERS = (
    health.router,
    query.router,
    conversations.router,
    classify.router,
    patent_risk.router,
    abs_api.router,
    tk.router,
    dossier.router,
    documents.router,
    corpus.router,
    receipts.router,
    speech.router,
    escalations.router,
    eval_api.router,
)
for router in API_ROUTERS:
    app.include_router(router, prefix="/v1")
