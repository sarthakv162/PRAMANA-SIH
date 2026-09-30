"""§6.4 `render`: build the `AnswerCard`/`RefusalCard` the client actually sees. This is the
one place both card types get assembled — backend never returns HTML/markdown, only these
structured objects (CLAUDE.md, §3 working agreement).
"""

from __future__ import annotations

from pathlib import Path

import yaml

from app.orchestrator.state import RequestState
from app.schemas.answer import (
    AnswerCard,
    AnswerSection,
    ConfidenceInfo,
    GlossaryEntry,
    TimingsMs,
    TranslationInfo,
)
from app.schemas.claims import Claim, Gap
from app.schemas.enums import ClaimStatus, Jurisdiction, Language, RefusalReason
from app.schemas.evidence import EvidenceSpan
from app.schemas.refusal import EscalationOffer, EscalationPrefill, RefusalCard
from app.verification.confidence import ConfidenceOutcome

DISCLAIMER = "Informational, not legal advice."

_JURISDICTION_HEADINGS = {"IN": "India", "INTL": "International"}


def build_refusal(
    state: RequestState,
    reason: RefusalReason,
    message: str,
    receipt_id: str,
) -> RefusalCard:
    nearest = [item.span for item in state.evidence_pack[:3]]
    return RefusalCard(
        request_id=state.request_id,
        reason=reason,
        message=message,
        nearest_sources=nearest,
        escalation=EscalationOffer(
            available=True,
            prefill=EscalationPrefill(
                question=state.scrubbed_query,
                jurisdiction=state.request.jurisdiction,
                as_of=state.as_of.isoformat(),
            ),
        ),
        receipt_id=receipt_id,
        disclaimer=DISCLAIMER,
    )


_GLOSSARY_CACHE: list[dict[str, object]] | None = None


def _glossary_entries() -> list[dict[str, object]]:
    global _GLOSSARY_CACHE
    if _GLOSSARY_CACHE is None:
        path = Path(__file__).resolve().parents[1] / "intake" / "glossary" / "terms.yaml"
        data = yaml.safe_load(path.read_text())
        _GLOSSARY_CACHE = data["terms"]
    return _GLOSSARY_CACHE


def _glossary_for_answer(claims: list[Claim], language: Language) -> list[GlossaryEntry]:
    """Locked terms that actually appear in the surviving claims' text, glossed in the
    answer's language (§6.3: legal terms stay in Latin script with a native gloss).
    """
    if language == Language.EN:
        return []
    combined_text = " ".join(c.text.lower() for c in claims)
    entries: list[GlossaryEntry] = []
    for term in _glossary_entries():
        term_en = str(term["term_en"])
        translations = term.get("translations")
        gloss = translations.get(language.value) if isinstance(translations, dict) else None
        if gloss and term_en.lower() in combined_text:
            entries.append(GlossaryEntry(term=term_en, gloss=str(gloss), lang=language))
    return entries


def _suggested_followups(state: RequestState) -> list[str]:
    """Deterministic templates pointing at routes the query didn't already take (§6.4)."""
    templates = {
        "classify": "Which regulatory category does my formulation fall under?",
        "patent_risk": "What is the patent risk under section 3(p)/3(e)/3(d) for this formulation?",
        "abs": "Do I have any access and benefit sharing obligations here?",
        "tk": "Does this match a known classical formulation?",
    }
    return [text for intent, text in templates.items() if intent != state.intent][:3]


def build_answer(
    state: RequestState,
    confidence: ConfidenceOutcome,
    timings_ms: TimingsMs,
    receipt_id: str,
) -> AnswerCard:
    evidence: dict[str, EvidenceSpan] = {}
    by_jurisdiction: dict[str, list[Claim]] = {j: [] for j in state.jurisdictions}
    span_by_evidence_id = {item.evidence_id: item.span for item in state.evidence_pack}

    for claim in state.verified_claims:
        span_jurisdiction = span_by_evidence_id[claim.evidence_ids[0]].jurisdiction
        by_jurisdiction.setdefault(span_jurisdiction, []).append(claim)
        for eid in claim.evidence_ids:
            evidence[eid] = span_by_evidence_id[eid]

    gaps = [Gap(text=g, status=ClaimStatus.NOT_IN_INDEXED_DOCUMENTS) for g in state.gaps]

    sections = [
        AnswerSection(
            jurisdiction=Jurisdiction(j),
            heading=_JURISDICTION_HEADINGS.get(j, j),
            claims=by_jurisdiction.get(j, []),
            gaps=gaps if j == state.jurisdictions[0] else [],
        )
        for j in state.jurisdictions
    ]

    return AnswerCard(
        request_id=state.request_id,
        corpus_version=state.corpus_version_label,
        as_of=state.as_of,
        language=state.lang,
        detected_language=state.lang,
        jurisdiction=state.request.jurisdiction,
        sections=sections,
        evidence=evidence,
        glossary=_glossary_for_answer(state.verified_claims, state.lang),
        confidence=ConfidenceInfo(level=confidence.level, score=confidence.score),
        review_recommended=confidence.review_recommended,
        dropped_claims=state.dropped_claims,
        translation=TranslationInfo(
            back_translation_ok=(state.lang == Language.EN) or bool(state.back_translation_ok),
            note=None,
        ),
        suggested_followups=_suggested_followups(state),
        receipt_id=receipt_id,
        disclaimer=DISCLAIMER,
        timings_ms=timings_ms,
    )
