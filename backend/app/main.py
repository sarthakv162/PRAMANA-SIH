"""PRAMANA backend entrypoint. Base path /v1 for every route (§5)."""

from __future__ import annotations

from fastapi import FastAPI

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
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging

configure_logging()

app = FastAPI(
    title="PRAMANA",
    description="Proof-carrying, multilingual assistant for Ayurvedic IP, ABS and "
    "drug-regulatory questions. Informational, not legal advice.",
    version="0.1.0",
)

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
