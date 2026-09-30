"""POST /v1/escalations, GET /v1/escalations (admin). See §5.3, §7.3 screen 14."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter

from app.config import get_settings
from app.core.errors import NotImplementedYet
from app.schemas.misc import EscalationRequest, EscalationResponse

router = APIRouter(tags=["escalations"])

_mock_tickets: list[dict[str, Any]] = []


@router.post("/escalations", response_model=EscalationResponse)
async def create_escalation(request: EscalationRequest) -> EscalationResponse:
    settings = get_settings()
    if not settings.mock_mode:
        raise NotImplementedYet("POST /escalations")
    ticket_id = f"tkt_{uuid.uuid4().hex[:12]}"
    _mock_tickets.append({"ticket_id": ticket_id, "status": "open", **request.model_dump()})
    return EscalationResponse(ticket_id=ticket_id, status="open")


@router.get("/escalations")
async def list_escalations() -> list[dict[str, Any]]:
    settings = get_settings()
    if not settings.mock_mode:
        raise NotImplementedYet("GET /escalations")
    return _mock_tickets
