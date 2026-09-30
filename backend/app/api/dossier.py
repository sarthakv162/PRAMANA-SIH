"""POST /v1/dossier — build a compliance dossier from stored results. Real renderers: M5 (§6.11)."""

from __future__ import annotations

from fastapi import APIRouter, Response

from app.config import get_settings
from app.core.errors import NotImplementedYet
from app.schemas.misc import DossierRequest

router = APIRouter(tags=["dossier"])

_MEDIA_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "md": "text/markdown",
}


@router.post("/dossier")
async def build_dossier(request: DossierRequest) -> Response:
    settings = get_settings()
    if not settings.mock_mode:
        raise NotImplementedYet("POST /dossier")
    placeholder = (
        f"# PRAMANA dossier (mock)\n\nItems: {', '.join(request.items)}\n"
        "Informational, not legal advice.\n"
    )
    return Response(
        content=placeholder.encode("utf-8"),
        media_type=_MEDIA_TYPES[request.format.value],
    )
