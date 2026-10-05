"""ABS (Access and Benefit Sharing) checker objects. See §5.5."""

from datetime import date
from typing import Literal

from pydantic import Field

from app.schemas.base import ContractModel
from app.schemas.decision_path import DecisionPath
from app.schemas.enums import AbsActivity, ApplicantType, Authority, Language
from app.schemas.evidence import EvidenceSpan


class AbsResource(ContractModel):
    species: str
    is_codified_tk: bool
    is_cultivated: bool
    state: str | None = None


class AbsRequest(ContractModel):
    applicant_type: ApplicantType
    activity: list[AbsActivity] = Field(min_length=1)
    resources: list[AbsResource] = Field(default_factory=list)
    ipr_type: str | None = None
    as_of: date | None = None
    language: Language = Language.AUTO


class AbsChecklistItem(ContractModel):
    id: str
    title: str
    authority: Authority
    form: str | None = None
    required: bool | None
    exempt: bool | None
    exempt_reason: str | None = None
    timing: str | None = None
    detail: str
    evidence_ids: list[str] = Field(default_factory=list)


class AbsResult(ContractModel):
    type: Literal["abs"] = "abs"
    summary: str
    assessment_status: Literal["unassessed", "provisional"] = "unassessed"
    checklist: list[AbsChecklistItem]
    decision_path: DecisionPath
    evidence: dict[str, EvidenceSpan]
    receipt_id: str
