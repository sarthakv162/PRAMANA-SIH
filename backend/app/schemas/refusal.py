"""RefusalCard. See §5.2."""

from typing import Literal

from pydantic import Field

from app.schemas.base import ContractModel
from app.schemas.enums import Jurisdiction, RefusalReason
from app.schemas.evidence import EvidenceSpan


class EscalationPrefill(ContractModel):
    question: str
    jurisdiction: Jurisdiction
    as_of: str


class EscalationOffer(ContractModel):
    available: bool
    prefill: EscalationPrefill | None = None


class RefusalCard(ContractModel):
    type: Literal["refusal"] = "refusal"
    request_id: str
    reason: RefusalReason
    message: str
    nearest_sources: list[EvidenceSpan] = Field(default_factory=list, max_length=3)
    escalation: EscalationOffer
    receipt_id: str
    disclaimer: str = "Informational, not legal advice."
