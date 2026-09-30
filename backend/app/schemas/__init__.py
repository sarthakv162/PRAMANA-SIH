"""Pydantic v2 contract models. See docs/IMPLEMENTATION_PLAN.md §5 (THE CONTRACT).

Every object and endpoint payload in §5 has a model here. `make contracts` exports
contracts/openapi.yaml from these; contracts/fixtures/*.json must each validate
against exactly one model (invariant I7, see tests/contract/).
"""

from app.schemas.abs import (
    AbsChecklistItem,
    AbsRequest,
    AbsResource,
    AbsResult,
)
from app.schemas.answer import (
    AnswerCard,
    AnswerSection,
    ConfidenceInfo,
    GlossaryEntry,
    TimingsMs,
    TranslationInfo,
)
from app.schemas.claims import Claim, ClaimChecks, Gap
from app.schemas.classify import (
    AbsPosture,
    ClassifyQuestion,
    ClassifyRequest,
    ClassifyResult,
    IpPosture,
    PostureItem,
    Progress,
    QuestionInput,
    Requirement,
)
from app.schemas.decision_path import DecisionEdge, DecisionNode, DecisionPath
from app.schemas.documents import CorpusVersionInfo, DocumentSummary
from app.schemas.enums import (
    AbsActivity,
    ApplicantType,
    Authority,
    ClaimStatus,
    ClassifyCategory,
    Confidence,
    CorpusVersionStatus,
    DocType,
    DossierFormat,
    InputKind,
    Jurisdiction,
    Language,
    Persona,
    QueryMode,
    RefusalReason,
    Risk,
    StageName,
    StageStatus,
)
from app.schemas.errors import ErrorBody, ErrorDetail
from app.schemas.eval import EvalCondition, EvalResults, RiskCoveragePoint
from app.schemas.evidence import EvidenceSpan, Highlight
from app.schemas.formulation import Formulation, Ingredient, ResourceOrigin
from app.schemas.health import HealthStatus, ModelsStatus
from app.schemas.misc import (
    DossierRequest,
    EscalationRequest,
    EscalationResponse,
    SpeechAsrResponse,
    SpeechTtsRequest,
)
from app.schemas.patent_risk import PatentRisk, PatentRiskRequest, PatentRiskSection, WhatWouldHelp
from app.schemas.query import QueryRequest, StageEvent
from app.schemas.receipts import ModelIds, Receipt, SpanVerification, VerifyResult
from app.schemas.refusal import EscalationOffer, EscalationPrefill, RefusalCard
from app.schemas.tk import (
    NormalizedIngredient,
    RadarAxis,
    RadarData,
    RegionalName,
    TkdlQuery,
    TkMatch,
    TkRadar,
    WatchlistHit,
)

__all__ = [
    "AbsActivity",
    "AbsChecklistItem",
    "AbsPosture",
    "AbsRequest",
    "AbsResource",
    "AbsResult",
    "AnswerCard",
    "AnswerSection",
    "ApplicantType",
    "Authority",
    "Claim",
    "ClaimChecks",
    "ClaimStatus",
    "ClassifyCategory",
    "ClassifyQuestion",
    "ClassifyRequest",
    "ClassifyResult",
    "Confidence",
    "ConfidenceInfo",
    "CorpusVersionInfo",
    "CorpusVersionStatus",
    "DecisionEdge",
    "DecisionNode",
    "DecisionPath",
    "DocType",
    "DocumentSummary",
    "DossierFormat",
    "DossierRequest",
    "ErrorBody",
    "ErrorDetail",
    "EscalationOffer",
    "EscalationPrefill",
    "EscalationRequest",
    "EscalationResponse",
    "EvalCondition",
    "EvalResults",
    "EvidenceSpan",
    "Formulation",
    "Gap",
    "GlossaryEntry",
    "HealthStatus",
    "Highlight",
    "Ingredient",
    "InputKind",
    "IpPosture",
    "Jurisdiction",
    "Language",
    "ModelIds",
    "ModelsStatus",
    "NormalizedIngredient",
    "PatentRisk",
    "PatentRiskRequest",
    "PatentRiskSection",
    "Persona",
    "PostureItem",
    "Progress",
    "QueryMode",
    "QueryRequest",
    "QuestionInput",
    "RadarAxis",
    "RadarData",
    "Receipt",
    "RefusalCard",
    "RefusalReason",
    "RegionalName",
    "Requirement",
    "ResourceOrigin",
    "Risk",
    "RiskCoveragePoint",
    "SpanVerification",
    "SpeechAsrResponse",
    "SpeechTtsRequest",
    "StageEvent",
    "StageName",
    "StageStatus",
    "TimingsMs",
    "TkMatch",
    "TkRadar",
    "TkdlQuery",
    "TranslationInfo",
    "VerifyResult",
    "WatchlistHit",
    "WhatWouldHelp",
]
