from __future__ import annotations

import secrets
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Header, Response
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.db import get_session
from app.core.errors import ApiError
from app.history import service
from app.schemas.history import (
    CaseOrder,
    CaseRef,
    ConversationCreate,
    ConversationDetail,
    ConversationSummary,
    SavedResult,
)


def authorize_workspace(x_demo_key: str = Header(default="")) -> None:
    settings = get_settings()
    if settings.public_demo_mode:
        return
    expected = settings.demo_key
    if not expected:
        raise ApiError("workspace_not_configured", "Configure DEMO_KEY to enable shared saved history.", 503)
    if not secrets.compare_digest(x_demo_key, expected):
        raise ApiError("unauthorized", "Enter the demo workspace key to access shared history.", 401)


router = APIRouter(tags=["history"], dependencies=[Depends(authorize_workspace)])


@router.post("/conversations", response_model=ConversationSummary, status_code=201)
def create(body: ConversationCreate, session: Session = Depends(get_session)) -> dict[str, Any]:
    return service.create_conversation(session, body.title)


@router.get("/conversations", response_model=list[ConversationSummary])
def list_saved(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    return service.list_conversations(session)


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def detail(conversation_id: UUID, session: Session = Depends(get_session)) -> dict[str, Any]:
    return service.conversation_detail(session, str(conversation_id))


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete(conversation_id: UUID, session: Session = Depends(get_session)) -> Response:
    service.require_conversation(session, str(conversation_id))
    session.execute(sa.delete(service.conversations).where(service.conversations.c.id == str(conversation_id)))
    session.commit()
    return Response(status_code=204)


@router.get("/requests/{request_id}", response_model=SavedResult)
def result(request_id: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    row = service.get_result(session, request_id)
    return {k: row[k] for k in SavedResult.model_fields}


@router.get("/case-file", response_model=list[CaseRef])
def case_file(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    return service.list_case_refs(session)


@router.post("/case-file/{request_id}", response_model=list[CaseRef])
def case_add(request_id: str, session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    return service.add_case_ref(session, request_id)


@router.delete("/case-file/{request_id}", response_model=list[CaseRef])
def case_remove(request_id: str, session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    session.execute(
        sa.delete(service.case_refs).where(
            service.case_refs.c.workspace_id == service.workspace(),
            service.case_refs.c.request_id == request_id,
        )
    )
    session.commit()
    return service.list_case_refs(session)


@router.put("/case-file", response_model=list[CaseRef])
def case_order(body: CaseOrder, session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    refs = service.list_case_refs(session)
    if len(set(body.request_ids)) != len(body.request_ids) or set(body.request_ids) != {r["request_id"] for r in refs}:
        raise ApiError("invalid_order", "Supply every current case-file request ID exactly once.", 409)
    for position, request_id in enumerate(body.request_ids):
        session.execute(
            sa.update(service.case_refs)
            .where(
                service.case_refs.c.workspace_id == service.workspace(),
                service.case_refs.c.request_id == request_id,
            )
            .values(position=position)
        )
    session.commit()
    return service.list_case_refs(session)
