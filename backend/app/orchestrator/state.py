"""Orchestrator request state (§6.4). One instance per `/query` call, threaded through every
node — nodes read what they need and write their own outputs, nothing more.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.core.deadline import Deadline
from app.generation.claim_schema import GenerationResult
from app.generation.resolve import ResolvedClaim
from app.retrieval.evidence_pack import NumberedSpan
from app.schemas.claims import Claim
from app.schemas.enums import Language, Persona
from app.schemas.query import QueryRequest


@dataclass
class RequestState:
    request_id: str
    raw_query: str  # never logged, never persisted (§6.3, I4) — only its scrubbed hash is
    request: QueryRequest

    # frame
    lang: Language = Language.EN
    jurisdictions: list[str] = field(default_factory=list)
    as_of: date = field(default_factory=date.today)
    persona: Persona = Persona.RESEARCHER

    # intake
    scrubbed_query: str = ""
    query_hash: str = ""
    query_en: str = ""
    conversation_context: str = ""

    # DB
    corpus_version_id: str = ""
    corpus_version_label: str = ""

    # route
    intent: str = "qa"
    direct_section_key: str | None = None

    # retrieve / resolve
    evidence_pack: list[NumberedSpan] = field(default_factory=list)
    used_dense_retrieval: bool = False
    retrieval_margin: float = 1.0

    # generate / resolve
    generation_unavailable: bool = False
    generation: GenerationResult | None = None
    verification_feedback: str = ""
    resolved_claims: list[ResolvedClaim] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    needs_clarification: str | None = None

    # verify
    verified_claims: list[Claim] = field(default_factory=list)
    dropped_claims: int = 0
    mean_entailment: float = 0.0

    # translation
    back_translation_ok: bool | None = None

    # render / audit
    result: dict[str, Any] | None = None  # the AnswerCard/RefusalCard, as a dict
    receipt_id: str = ""

    deadline: Deadline = field(default_factory=lambda: Deadline(45.0))
    stage_timings_ms: dict[str, int] = field(default_factory=dict)
