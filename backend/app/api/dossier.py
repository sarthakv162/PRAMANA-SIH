"""POST /v1/dossier — build a compliance dossier from stored results (§6.11).

Real mode never re-runs the pipeline: each `request_id` in `items` is looked up in the audit
log (`audit/receipts.py::latest_result_for_request`), which holds the exact response that was
served at the time — a dossier is a formatted export of what was actually shown, not a fresh
answer.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.audit.receipts import StoredResult, latest_result_for_request
from app.config import get_settings
from app.core.db import get_session
from app.core.fixtures import load_fixture
from app.render.docx import render_docx
from app.render.dossier import DossierItem, build_dossier_item, missing_item
from app.render.md import render_md
from app.render.pdf import render_pdf
from app.schemas.misc import DossierRequest

router = APIRouter(tags=["dossier"])

_MEDIA_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "md": "text/markdown",
}

_RENDERERS = {
    "pdf": render_pdf,
    "docx": render_docx,
    "md": render_md,
}


def _mock_dossier_item(request_id: str) -> DossierItem:
    """Render the answer fixture only for its own request ID; unknown IDs stay explicit."""
    for fixture_name in ("answer_card_in.json", "answer_card_both_hi.json"):
        result = load_fixture(fixture_name)
        if request_id != result["request_id"]:
            continue
        receipt = load_fixture("receipt.json")
        stored = StoredResult(
            request_id=request_id,
            receipt_id=result["receipt_id"],
            entry_hash=receipt["entry_hash"],
            result=result,
            request_payload=None,
        )
        return build_dossier_item(stored)
    return missing_item(request_id)


@router.post("/dossier")
async def build_dossier(
    request: DossierRequest, session: Session = Depends(get_session)
) -> Response:
    settings = get_settings()
    if settings.mock_mode:
        items = [_mock_dossier_item(request_id) for request_id in request.items]
    else:
        items = [
            build_dossier_item(stored)
            if (stored := latest_result_for_request(session, request_id)) is not None
            else missing_item(request_id)
            for request_id in request.items
        ]
    content = _RENDERERS[request.format.value](items, request.language.value)
    return Response(content=content, media_type=_MEDIA_TYPES[request.format.value])
