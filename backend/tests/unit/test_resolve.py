"""Unit tests for generation/resolve.py — the boundary where model output stops being
trusted at face value (§6.6).
"""

from __future__ import annotations

from datetime import date

from app.generation.claim_schema import GenerationResult, RawClaim
from app.generation.resolve import resolve_generation
from app.retrieval.evidence_pack import NumberedSpan
from app.schemas.evidence import EvidenceSpan


def _span(evidence_id: str, jurisdiction: str) -> EvidenceSpan:
    return EvidenceSpan(
        id=evidence_id,
        doc_id="patents_act_1970",
        doc_title="The Patents Act, 1970",
        doc_type="statute",
        jurisdiction=jurisdiction,
        citation_label="Patents Act, 1970 — s.3(p)",
        section_key="patents_act_1970#s3(p)",
        section_path=["Section 3", "clause (p)"],
        page=9,
        page_end=9,
        char_start=0,
        char_end=10,
        text="some text",
        sha256="abc",
        effective_from=date(1970, 4, 20),
        corpus_version="v1",
        source_url="https://example.org",
        pdf_url="/v1/documents/patents_act_1970/pdf",
    )


def test_resolves_claim_with_valid_reference() -> None:
    span_a = NumberedSpan(number=1, evidence_id="ev_a", chunk_id="c_a", span=_span("ev_a", "IN"))
    numbered = [span_a]
    gen = GenerationResult(claims=[RawClaim(statement="A claim.", evidence_ids=["E1"])])

    outcome = resolve_generation(gen, numbered)

    assert len(outcome.resolved) == 1
    assert outcome.resolved[0].evidence_ids == ["ev_a"]
    assert outcome.resolved[0].jurisdiction == "IN"
    assert outcome.dropped == []


def test_drops_claim_citing_id_outside_pack() -> None:
    span_a = NumberedSpan(number=1, evidence_id="ev_a", chunk_id="c_a", span=_span("ev_a", "IN"))
    numbered = [span_a]
    gen = GenerationResult(claims=[RawClaim(statement="A claim.", evidence_ids=["E9"])])

    outcome = resolve_generation(gen, numbered)

    assert outcome.resolved == []
    assert len(outcome.dropped) == 1


def test_drops_claim_mixing_jurisdictions() -> None:
    numbered = [
        NumberedSpan(number=1, evidence_id="ev_a", chunk_id="c_a", span=_span("ev_a", "IN")),
        NumberedSpan(number=2, evidence_id="ev_b", chunk_id="c_b", span=_span("ev_b", "INTL")),
    ]
    gen = GenerationResult(claims=[RawClaim(statement="A claim.", evidence_ids=["E1", "E2"])])

    outcome = resolve_generation(gen, numbered)

    assert outcome.resolved == []
    assert "jurisdiction" in outcome.dropped[0]


def test_gaps_and_needs_clarification_pass_through() -> None:
    numbered: list[NumberedSpan] = []
    gen = GenerationResult(gaps=["Fee amounts not covered."], needs_clarification="Which state?")

    outcome = resolve_generation(gen, numbered)

    assert outcome.gaps == ["Fee amounts not covered."]
    assert outcome.needs_clarification == "Which state?"
