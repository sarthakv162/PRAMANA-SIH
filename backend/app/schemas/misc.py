"""Small request/response shapes not big enough for their own module. See §5.3."""

from app.schemas.base import ContractModel
from app.schemas.enums import DossierFormat, Language


class SpeechAsrResponse(ContractModel):
    text: str
    language: Language


class SpeechTtsRequest(ContractModel):
    text: str
    language: Language = Language.AUTO


class DossierRequest(ContractModel):
    items: list[str]
    format: DossierFormat = DossierFormat.PDF
    language: Language = Language.AUTO


class EscalationRequest(ContractModel):
    request_id: str
    contact: str | None = None
    note: str | None = None


class EscalationResponse(ContractModel):
    ticket_id: str
    status: str
