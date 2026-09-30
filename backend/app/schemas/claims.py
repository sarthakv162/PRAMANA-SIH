"""Claim and Gap — see §5.2. `Claim.text` is a model-written paraphrase, never a quote."""

from pydantic import Field

from app.schemas.base import ContractModel
from app.schemas.enums import ClaimStatus


class ClaimChecks(ContractModel):
    nli_entail: float = Field(ge=0.0, le=1.0)
    numbers_ok: bool
    dates_ok: bool
    negation_ok: bool


class Claim(ContractModel):
    id: str
    text: str
    status: ClaimStatus
    evidence_ids: list[str] = Field(min_length=1)
    checks: ClaimChecks


class Gap(ContractModel):
    text: str
    status: ClaimStatus = ClaimStatus.NOT_IN_INDEXED_DOCUMENTS
