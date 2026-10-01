"""PRAMANA backend entrypoint. Base path /v1 for every route (§5)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from app.api import abs as abs_api
from app.api import (
    classify,
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
from app.core.logging import configure_logging
from app.core.rate_limit import RateLimiter

configure_logging()

app = FastAPI(
    title="PRAMANA",
    description="Proof-carrying, multilingual assistant for Ayurvedic IP, ABS and "
    "drug-regulatory questions. Informational, not legal advice.",
    version="0.1.0",
)

_rate_limiter = RateLimiter(
    requests=get_settings().rate_limit_requests,
    window_s=get_settings().rate_limit_window_s,
)


@app.middleware("http")
async def enforce_ip_rate_limit(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
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

for router in (
    health.router,
    query.router,
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
):
    app.include_router(router, prefix="/v1")
