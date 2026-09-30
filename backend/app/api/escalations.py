"""POST /v1/escalations, GET /v1/escalations (admin). See §5.3, §7.3 screen 14.

Real-mode logic lives in `app/escalations.py`; this module is just the mock/real dispatch,
matching the split already used for `/receipts` (`audit/receipts.py`).
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import escalations as escalations_store
from app.config import get_settings
from app.core.db import get_session
from app.schemas.misc import EscalationRequest, EscalationResponse

router = APIRouter(tags=["escalations"])

_mock_tickets: list[dict[str, Any]] = []


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


@router.get("/escalations")
async def list_escalations(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    settings = get_settings()
    if settings.mock_mode:
        return _mock_tickets

    return escalations_store.list_escalations(session)
