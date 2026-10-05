"""QueryRequest and SSE stage events for POST /v1/query. See §5.4."""

from datetime import date
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas.base import ContractModel
from app.schemas.enums import Jurisdiction, Language, Persona, QueryMode, StageName, StageStatus
from app.schemas.formulation import Formulation


class QueryRequest(ContractModel):
    query: str = Field(min_length=1, max_length=6000)
    jurisdiction: Jurisdiction = Jurisdiction.BOTH
    as_of: date | None = None
    language: Language = Language.AUTO
    persona: Persona = Persona.RESEARCHER
    mode: QueryMode = QueryMode.TEXT
    conversation_id: str | None = None
    formulation: Formulation | None = None

    @field_validator("conversation_id")
    @classmethod
    def valid_conversation(cls, value: str | None) -> str | None:
        return str(UUID(value)) if value else None


class StageEvent(ContractModel):
    name: StageName
    status: StageStatus
    ms: int | None = None
