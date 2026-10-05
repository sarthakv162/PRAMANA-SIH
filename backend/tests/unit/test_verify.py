"""Verification integration tests for claims that cite clause-level evidence."""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

from app.generation.resolve import ResolvedClaim
from app.schemas.enums import DocType
from app.schemas.evidence import EvidenceSpan
from app.verification.nli import NliResult
from app.verification.verify import verify_claim


def test_clause_verification_uses_and_cites_parent_context() -> None:
    evidence_id = "ev_patents_3p"
    evidence = EvidenceSpan(
        id=evidence_id,
        doc_id="patents_act_1970",
        doc_title="The Patents Act, 1970",
        doc_type=DocType.STATUTE,
        jurisdiction="IN",
        citation_label="The Patents Act, 1970 — s.3(p)",
        section_key="patents_act_1970#s3(p)",
        section_path=["Chapter II", "Section 3", "What are not inventions", "clause (p)"],
        page=10,
        page_end=10,
        char_start=0,
        char_end=81,
        text="An invention which, in effect, is traditional knowledge.",
        sha256="0" * 64,
        effective_from=date(1970, 4, 20),
        corpus_version="test",
        source_url="https://example.test/patents.pdf",
        pdf_url="/v1/documents/patents_act_1970/pdf",
    )
    parent = evidence.model_copy(
        update={
            "id": "ev_patents_s3",
            "citation_label": "The Patents Act, 1970 — s.3",
            "section_key": "patents_act_1970#s3",
            "section_path": ["Chapter II", "Section 3", "What are not inventions"],
            "text": "The following are not inventions within the meaning of this Act.",
        }
    )
    resolved = ResolvedClaim(
        statement="Section 3(p) excludes traditional knowledge from patentability.",
        evidence_ids=[evidence_id],
        jurisdiction="IN",
        kind="statement",
    )

    with patch(
        "app.verification.verify.entailment_score",
        return_value=NliResult(entailment=0.95, neutral=0.03, contradiction=0.02),
    ) as entailment:
        claim = verify_claim("c1", resolved, {evidence_id: evidence, parent.id: parent})

    assert claim is not None
    assert claim.checks.numbers_ok is True
    assert claim.evidence_ids == [parent.id, evidence_id]
    assert "The following are not inventions" in entailment.call_args.args[0]


def test_oversized_nli_premise_is_not_silently_truncated(monkeypatch) -> None:
    from types import SimpleNamespace

    from app.verification import nli

    class Tokenizer:
        def __call__(self, premise, hypothesis, **kwargs):
            assert kwargs["truncation"] is False
            return {"input_ids": SimpleNamespace(shape=(1, 513))}

    def model(*args, **kwargs):
        raise AssertionError("Oversized evidence must not be certified")

    monkeypatch.setattr(nli, "_model_and_tokenizer", lambda: (model, Tokenizer()))
    assert nli.entailment_score("long source", "claim").entailment == 0


def test_partial_claims_do_not_count_as_verified_confidence(monkeypatch) -> None:
    from app.orchestrator.nodes import verify as node
    from app.orchestrator.state import RequestState
    from app.schemas.claims import Claim, ClaimChecks
    from app.schemas.enums import ClaimStatus
    from app.schemas.query import QueryRequest
    from app.verification.verify import VerificationOutcome

    claim = Claim(
        id="c1",
        text="Partly supported statement",
        status=ClaimStatus.PARTIAL,
        evidence_ids=["e1"],
        checks=ClaimChecks(nli_entail=0.7, numbers_ok=True, dates_ok=True, negation_ok=True),
    )
    outcome = VerificationOutcome(claims=[claim], dropped_count=0, mean_entailment=0.7, drop_reasons={})
    monkeypatch.setattr(node, "verify_claims", lambda *args: outcome)
    state = RequestState(request_id="test", raw_query="", request=QueryRequest(query="Legal topic"))
    state.resolved_claims = [ResolvedClaim("Partly supported statement", ["e1"], "IN", "statement")]
    confidence = node.run(state)
    assert confidence.score < 0.6 and confidence.review_recommended
