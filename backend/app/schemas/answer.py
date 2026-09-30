"""AnswerCard and its parts. See §5.2."""

from datetime import date
from typing import Literal

from pydantic import Field

from app.schemas.base import ContractModel
from app.schemas.claims import Claim, Gap
from app.schemas.enums import Confidence, Jurisdiction, Language
from app.schemas.evidence import EvidenceSpan


class GlossaryEntry(ContractModel):
    term: str
    gloss: str
    lang: Language


class ConfidenceInfo(ContractModel):
    level: Confidence
    score: float = Field(ge=0.0, le=1.0)


class TranslationInfo(ContractModel):
    back_translation_ok: bool
    note: str | None = None


class TimingsMs(ContractModel):
    intake: int
    retrieve: int
    generate: int
    verify: int
    total: int


class AnswerSection(ContractModel):
    jurisdiction: Jurisdiction
    heading: str
    claims: list[Claim]
    gaps: list[Gap] = Field(default_factory=list)


class AnswerCard(ContractModel):
    type: Literal["answer"] = "answer"
    request_id: str
    corpus_version: str
    as_of: date
    language: Language
    detected_language: Language
    jurisdiction: Jurisdiction
    sections: list[AnswerSection]
    evidence: dict[str, EvidenceSpan]
    glossary: list[GlossaryEntry] = Field(default_factory=list)
    confidence: ConfidenceInfo
    review_recommended: bool = False
    dropped_claims: int = 0
    translation: TranslationInfo
    suggested_followups: list[str] = Field(default_factory=list)
    receipt_id: str
    disclaimer: str = "Informational, not legal advice."
    timings_ms: TimingsMs
