"""Escalation-to-human-facilitator store (§6.1 `escalations` table, §7.3 screen 14).

Split from `api/escalations.py` the same way `audit/receipts.py` is split from
`api/receipts.py`: the DB logic lives here, independent of request/response plumbing, so it
can be unit-tested directly against a real session without needing `MOCK_MODE` toggled (the
app-wide `Settings` object is `@lru_cache`'d, so tests can't flip it mid-suite).
"""

from __future__ import annotations

import uuid
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.schemas.misc import EscalationRequest, EscalationResponse

_escalations_table = sa.Table(
    "escalations",
    sa.MetaData(),
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("request_id", UUID(as_uuid=True)),
    sa.Column("contact", sa.Text),
    sa.Column("note", sa.Text),
    sa.Column("status", sa.Text),
    sa.Column("created_at", sa.DateTime(timezone=True)),
)

_requests_table = sa.Table("requests", sa.MetaData(), sa.Column("id", UUID(as_uuid=True), primary_key=True))


def _ticket_id(escalation_id: uuid.UUID) -> str:
    return f"tkt_{escalation_id.hex[:12]}"


def create_escalation(session: Session, request: EscalationRequest) -> EscalationResponse:
    """Raises `ApiError` (400 for a malformed id, 404 for one that doesn't exist) rather than
    letting a bad `request_id` reach Postgres as an invalid-UUID DB error.
    """
    try:
        request_uuid = uuid.UUID(request.request_id)
    except ValueError as exc:
        raise ApiError(
            code="invalid_request_id",
            message=f"{request.request_id!r} is not a valid request id.",
            status_code=400,
        ) from exc

    exists = session.execute(sa.select(_requests_table.c.id).where(_requests_table.c.id == request_uuid)).first()
    if exists is None:
        raise ApiError(
            code="request_not_found",
            message=f"no request {request.request_id!r} — it must come from a prior "
            "/query, /classify, /patent-risk, /abs-check, or /tk-radar response.",
            status_code=404,
        )

    escalation_id = uuid.uuid4()
    session.execute(
        sa.insert(_escalations_table).values(
            id=escalation_id,
            request_id=request_uuid,
            contact=request.contact,
            note=request.note,
            status="open",
        )
    )
    session.commit()
    return EscalationResponse(ticket_id=_ticket_id(escalation_id), status="open")


def list_escalations(session: Session) -> list[dict[str, Any]]:
    rows = session.execute(sa.select(_escalations_table).order_by(_escalations_table.c.created_at.desc())).all()
    return [
        {
            "ticket_id": _ticket_id(row.id),
            "request_id": str(row.request_id),
            "contact": row.contact,
            "note": row.note,
            "status": row.status,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]
