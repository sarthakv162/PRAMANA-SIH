"""POST /v1/escalations, GET /v1/escalations (admin). See §5.3, §7.3 screen 14.

Real-mode logic lives in `app/escalations.py`; this module is just the mock/real dispatch,
matching the split already used for `/receipts` (`audit/receipts.py`).
"""

from __future__ import annotations

import hmac
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app import escalations as escalations_store
from app.config import get_settings
from app.core.db import get_session
from app.core.errors import ApiError
from app.schemas.misc import EscalationRequest, EscalationResponse

router = APIRouter(tags=["escalations"])

_mock_tickets: list[dict[str, Any]] = []


def require_admin_key(x_demo_key: str | None = Header(default=None, alias="X-Demo-Key")) -> None:
    """Fail closed for the admin listing when no key has been configured."""
    expected = get_settings().demo_key
    if not expected:
        raise ApiError(
            code="admin_auth_not_configured",
            message="The escalation admin endpoint is disabled until DEMO_KEY is configured.",
            status_code=503,
        )
    supplied = x_demo_key or ""
    if not hmac.compare_digest(supplied, expected):
        raise ApiError(code="unauthorized", message="A valid X-Demo-Key is required.", status_code=401)


@router.post("/escalations", response_model=EscalationResponse)
async def create_escalation(
    request: EscalationRequest, session: Session = Depends(get_session)
) -> EscalationResponse:
    settings = get_settings()
    if settings.mock_mode:
        ticket_id = f"tkt_{uuid.uuid4().hex[:12]}"
        _mock_tickets.append({"ticket_id": ticket_id, "status": "open", **request.model_dump()})
        return EscalationResponse(ticket_id=ticket_id, status="open")

    return escalations_store.create_escalation(session, request)


@router.get("/escalations", dependencies=[Depends(require_admin_key)])
async def list_escalations(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    settings = get_settings()
    if settings.mock_mode:
        return _mock_tickets

    return escalations_store.list_escalations(session)
