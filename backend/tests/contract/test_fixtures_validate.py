"""Invariant I7: every fixture in contracts/fixtures/ validates against its Pydantic model,
so fixtures can never silently drift from the contract (docs/IMPLEMENTATION_PLAN.md §3, §11).
"""

from __future__ import annotations

import json

import pytest

from app.schemas.abs import AbsResult
from app.schemas.answer import AnswerCard
from app.schemas.classify import ClassifyQuestion, ClassifyResult
from app.schemas.errors import ErrorBody
from app.schemas.eval import EvalResults
from app.schemas.misc import SpeechAsrResponse
from app.schemas.patent_risk import PatentRisk
from app.schemas.receipts import Receipt, VerifyResult
from app.schemas.refusal import RefusalCard
from app.schemas.tk import TkRadar
from tests.conftest import FIXTURES_DIR

FIXTURE_MODEL_MAP = {
    "answer_card_in.json": AnswerCard,
    "answer_card_both_hi.json": AnswerCard,
    "refusal_no_evidence.json": RefusalCard,
    "refusal_legal_advice.json": RefusalCard,
    "classify_question.json": ClassifyQuestion,
    "classify_result_classical.json": ClassifyResult,
    "classify_result_new_drug.json": ClassifyResult,
    "patent_risk_high.json": PatentRisk,
    "patent_risk_low.json": PatentRisk,
    "abs_result.json": AbsResult,
    "tk_radar.json": TkRadar,
    "receipt.json": Receipt,
    "verify_ok.json": VerifyResult,
    "verify_tampered.json": VerifyResult,
    "eval_results.json": EvalResults,
    "error.json": ErrorBody,
    "speech_asr_hi.json": SpeechAsrResponse,
}


def test_fixture_checklist_matches_disk() -> None:
    """§5.6's fixture checklist (minus sse_transcript.txt, checked separately) is complete."""
    on_disk = {p.name for p in FIXTURES_DIR.glob("*.json")}
    assert on_disk == set(FIXTURE_MODEL_MAP)


@pytest.mark.parametrize("fixture_name", sorted(FIXTURE_MODEL_MAP))
def test_fixture_validates_against_model(fixture_name: str) -> None:
    model = FIXTURE_MODEL_MAP[fixture_name]
    data = json.loads((FIXTURES_DIR / fixture_name).read_text())
    model.model_validate(data)


def test_sse_transcript_exists() -> None:
    path = FIXTURES_DIR / "sse_transcript.txt"
    assert path.exists()
    assert path.read_text().strip()


def test_verify_tampered_has_a_failing_span() -> None:
    """verify_tampered.json must actually demonstrate the failure path (§6.9)."""
    data = json.loads((FIXTURES_DIR / "verify_tampered.json").read_text())
    result = VerifyResult.model_validate(data)
    assert any(not span.merkle_proof_valid for span in result.spans)


def test_verify_ok_has_no_failing_spans() -> None:
    data = json.loads((FIXTURES_DIR / "verify_ok.json").read_text())
    result = VerifyResult.model_validate(data)
    assert result.chain_valid
    assert all(span.merkle_proof_valid for span in result.spans)


@pytest.mark.parametrize("fixture_name", ["answer_card_in.json", "answer_card_both_hi.json"])
def test_answer_card_evidence_ids_resolve(fixture_name: str) -> None:
    """Every evidence_id a claim/gap cites must exist in the same fixture's evidence map."""
    data = json.loads((FIXTURES_DIR / fixture_name).read_text())
    known_ids = set(data["evidence"])
    for section in data["sections"]:
        for claim in section["claims"]:
            for eid in claim["evidence_ids"]:
                assert eid in known_ids, f"{fixture_name}: claim cites unknown evidence id {eid}"
