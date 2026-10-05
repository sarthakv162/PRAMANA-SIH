from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import Field

from app.schemas.base import ContractModel


class ConversationCreate(ContractModel):
    title: str = Field(default="New conversation", max_length=200)


class ConversationSummary(ContractModel):
    id: UUID
    title: str
    workspace_id: str
    created_at: datetime
    updated_at: datetime
    expires_at: datetime


class SavedResult(ContractModel):
    request_id: str
    conversation_id: UUID | None = None
    result: dict[str, Any]
    receipt_id: str
    created_at: datetime
    expires_at: datetime


class SavedMessage(ContractModel):
    id: UUID
    role: Literal["user", "assistant"]
    content: str
    request_id: str | None = None
    created_at: datetime
    result: dict[str, Any] | None = None


class ConversationDetail(ConversationSummary):
    messages: list[SavedMessage]


class CaseRef(ContractModel):
    request_id: str
    summary: str
    receipt_id: str | None = None


class CaseOrder(ContractModel):
    request_ids: list[str]
