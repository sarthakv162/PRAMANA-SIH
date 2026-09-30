"""QueryRequest and SSE stage events for POST /v1/query. See §5.4."""

from datetime import date

from app.schemas.base import ContractModel
from app.schemas.enums import Jurisdiction, Language, Persona, QueryMode, StageName, StageStatus
from app.schemas.formulation import Formulation


class QueryRequest(ContractModel):
    query: str
    jurisdiction: Jurisdiction = Jurisdiction.BOTH
    as_of: date | None = None
    language: Language = Language.AUTO
    persona: Persona = Persona.RESEARCHER
    mode: QueryMode = QueryMode.TEXT
    conversation_id: str | None = None
    formulation: Formulation | None = None


class StageEvent(ContractModel):
    name: StageName
    status: StageStatus
    ms: int | None = None
