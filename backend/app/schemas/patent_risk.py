"""PatentRisk — 3(p)/3(e)/3(d) risk indicator. See §5.2, §6.8."""

from datetime import date
from typing import Literal

from pydantic import Field

from app.schemas.base import ContractModel
from app.schemas.decision_path import DecisionPath
from app.schemas.enums import Language, Risk
from app.schemas.evidence import EvidenceSpan
from app.schemas.formulation import Formulation


class PatentRiskRequest(Formulation):
    """Formulation + as_of/language, per §5.3: `Formulation (+ as_of, language) -> PatentRisk`."""

    as_of: date | None = None
    language: Language = Language.AUTO


class PatentRiskSection(ContractModel):
    section: str
    risk: Risk
    triggered_rules: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class WhatWouldHelp(ContractModel):
    text: str
    evidence_ids: list[str] = Field(default_factory=list)


class PatentRisk(ContractModel):
    type: Literal["patent_risk"] = "patent_risk"
    gauge: Risk
    score: float = Field(ge=0.0, le=1.0)
    per_section: list[PatentRiskSection]
    what_would_help: list[WhatWouldHelp] = Field(default_factory=list)
    decision_path: DecisionPath
    evidence: dict[str, EvidenceSpan]
    receipt_id: str
    disclaimer: str = "Informational, not legal advice."
