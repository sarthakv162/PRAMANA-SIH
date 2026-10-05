"""Enums shared across the contract. See docs/IMPLEMENTATION_PLAN.md §5.1."""

from enum import StrEnum


class Jurisdiction(StrEnum):
    IN = "IN"
    INTL = "INTL"
    BOTH = "BOTH"


class Language(StrEnum):
    AUTO = "auto"
    EN = "en"
    HI = "hi"
    TA = "ta"
    BN = "bn"
    MR = "mr"
    TE = "te"
    GU = "gu"
    KN = "kn"
    ML = "ml"
    PA = "pa"
    OR = "or"


class Persona(StrEnum):
    VAIDYA = "vaidya"
    STARTUP = "startup"
    ATTORNEY = "attorney"
    LICENSING_OFFICER = "licensing_officer"
    RESEARCHER = "researcher"


class ClaimStatus(StrEnum):
    VERIFIED = "verified"
    PARTIAL = "partial"
    NOT_IN_INDEXED_DOCUMENTS = "not_in_indexed_documents"


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Risk(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class DocType(StrEnum):
    STATUTE = "statute"
    RULE = "rule"
    REGULATION = "regulation"
    TREATY = "treaty"
    NOTIFICATION = "notification"
    CASE = "case"
    GUIDELINE = "guideline"
    MANUAL = "manual"


class RefusalReason(StrEnum):
    GENERATION_UNAVAILABLE = "generation_unavailable"
    NO_EVIDENCE = "no_evidence"
    OUT_OF_SCOPE = "out_of_scope"
    LOW_CONFIDENCE = "low_confidence"
    LEGAL_ADVICE_REQUEST = "legal_advice_request"
    JURISDICTION_UNCLEAR = "jurisdiction_unclear"
    DEADLINE_EXCEEDED = "deadline_exceeded"


class QueryMode(StrEnum):
    TEXT = "text"
    VOICE = "voice"


class ClassifyCategory(StrEnum):
    CLASSICAL = "classical"
    PROPRIETARY = "proprietary"
    NEW_DRUG = "new_drug"
    PHYTOPHARMACEUTICAL = "phytopharmaceutical"
    AAHAR_NUTRACEUTICAL = "aahar_nutraceutical"
    COSMETIC = "cosmetic"


class InputKind(StrEnum):
    SINGLE = "single"
    MULTI = "multi"
    BOOLEAN = "boolean"
    TEXT = "text"


class Authority(StrEnum):
    NBA = "NBA"
    SBB = "SBB"
    BMC = "BMC"
    NONE = "none"


class AbsActivity(StrEnum):
    RESEARCH = "research"
    COMMERCIAL_UTILISATION = "commercial_utilisation"
    IPR_APPLICATION = "ipr_application"
    TRANSFER_RESULTS = "transfer_results"
    EXPORT = "export"
    CULTIVATION_TRADE = "cultivation_trade"


class ApplicantType(StrEnum):
    INDIAN_CITIZEN = "indian_citizen"
    INDIAN_COMPANY = "indian_company"
    FOREIGN_ENTITY = "foreign_entity"
    NRI = "nri"


class DossierFormat(StrEnum):
    PDF = "pdf"
    DOCX = "docx"
    MD = "md"


class StageName(StrEnum):
    INTAKE = "intake"
    FRAME = "frame"
    CACHE = "cache"
    ROUTE = "route"
    RETRIEVE = "retrieve"
    RESOLVE = "resolve"
    GENERATE = "generate"
    VERIFY = "verify"
    RENDER = "render"
    AUDIT = "audit"


class StageStatus(StrEnum):
    RUNNING = "running"
    DONE = "done"
    SKIPPED = "skipped"
    FAILED = "failed"


class CorpusVersionStatus(StrEnum):
    STAGED = "staged"
    LIVE = "live"
    RETIRED = "retired"
