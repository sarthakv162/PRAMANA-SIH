"""Small request/response shapes not big enough for their own module. See §5.3."""

from pydantic import Field, field_validator

from app.schemas.base import ContractModel
from app.schemas.enums import DossierFormat, Language


class SpeechAsrResponse(ContractModel):
    text: str
    language: Language


class SpeechTtsRequest(ContractModel):
    text: str = Field(min_length=1, max_length=2500)
    language: Language = Language.AUTO

    @field_validator("text")
    @classmethod
    def nonblank_speech(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Speech text must not be blank")
        return value.strip()


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
