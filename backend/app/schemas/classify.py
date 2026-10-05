"""Classification wizard objects. See §5.2, §5.6. `/classify` is stateless (§6.8)."""

from datetime import date
from typing import Literal

from pydantic import Field

from app.schemas.base import ContractModel
from app.schemas.decision_path import DecisionPath
from app.schemas.enums import ClassifyCategory, InputKind, Jurisdiction, Language, Risk
from app.schemas.evidence import EvidenceSpan


class InputOption(ContractModel):
    value: str
    label: str


class QuestionField(ContractModel):
    id: str
    label: str
    kind: InputKind
    options: list[InputOption] = Field(default_factory=list)
    required: bool = True


class QuestionInput(ContractModel):
    kind: InputKind
    options: list[InputOption] = Field(default_factory=list)
    fields: list[QuestionField] = Field(default_factory=list)


class Progress(ContractModel):
    answered: int
    estimated_total: int


class ClassifyQuestion(ContractModel):
    type: Literal["question"] = "question"
    question_id: str
    text: str
    why_asked: str
    input: QuestionInput
    evidence_ids: list[str] = Field(default_factory=list)
    evidence: dict[str, EvidenceSpan] = Field(default_factory=dict)
    progress: Progress


class Requirement(ContractModel):
    text: str
    evidence_ids: list[str] = Field(default_factory=list)


class PostureItem(ContractModel):
    risk: Risk
    note: str
    evidence_ids: list[str] = Field(default_factory=list)


class IpPosture(ContractModel):
    patent: PostureItem
    gi: PostureItem
    trademark: PostureItem
    design: PostureItem
    copyright: PostureItem
    trade_secret: PostureItem


class AbsPosture(ContractModel):
    summary: str
    evidence_ids: list[str] = Field(default_factory=list)


class ClassifyRequest(ContractModel):
    answers: dict[str, str] = Field(default_factory=dict)
    jurisdiction: Jurisdiction = Jurisdiction.BOTH
    as_of: date | None = None
    language: Language = Language.AUTO


class ClassifyResult(ContractModel):
    type: Literal["result"] = "result"
    status: Literal["provisional", "draft"] = "provisional"
    review_recommended: bool = True
    missing_information: list[str] = Field(default_factory=list)
    category: ClassifyCategory
    category_label: str
    requirements: list[Requirement]
    ip_posture: IpPosture
    abs_posture: AbsPosture
    decision_path: DecisionPath
    evidence: dict[str, EvidenceSpan]
    receipt_id: str
