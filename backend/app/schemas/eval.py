"""EvalResults — served by GET /eval/latest, consumed by the Eval screen. See §5.2, §9."""

from datetime import datetime

from pydantic import Field

from app.schemas.base import ContractModel


class EvalCondition(ContractModel):
    name: str
    citation_precision: float = Field(ge=0.0, le=1.0)
    citation_recall: float = Field(ge=0.0, le=1.0)
    # Null means this run did not evaluate generated claims (for example, retrieval-only eval).
    faithfulness: float | None = Field(default=None, ge=0.0, le=1.0)
    abstention_accuracy: float = Field(ge=0.0, le=1.0)
    jurisdiction_leaks: int = Field(ge=0)


class RiskCoveragePoint(ContractModel):
    threshold: float
    coverage: float = Field(ge=0.0, le=1.0)
    risk: float = Field(ge=0.0, le=1.0)


class EvalResults(ContractModel):
    run_id: str
    corpus_version: str
    n_questions: int
    method: str | None = None
    conditions: list[EvalCondition]
    risk_coverage: list[RiskCoveragePoint] = Field(default_factory=list)
    generated_at: datetime
