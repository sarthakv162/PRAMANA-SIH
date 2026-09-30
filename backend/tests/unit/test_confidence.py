"""Unit tests for verification/confidence.py (§6.7)."""

from __future__ import annotations

from app.verification.confidence import compute_confidence


def test_high_signals_give_high_confidence_no_abstain() -> None:
    outcome = compute_confidence(
        retrieval_margin=0.9, mean_entailment=0.95, verified_ratio=1.0, back_translation_ok=True
    )
    assert outcome.level.value == "high"
    assert outcome.abstain is False
    assert outcome.review_recommended is False


def test_low_signals_trigger_abstain() -> None:
    outcome = compute_confidence(
        retrieval_margin=0.05, mean_entailment=0.1, verified_ratio=0.0, back_translation_ok=False
    )
    assert outcome.level.value == "low"
    assert outcome.abstain is True


def test_middling_signals_trigger_review_not_abstain() -> None:
    outcome = compute_confidence(
        retrieval_margin=0.5, mean_entailment=0.5, verified_ratio=0.5, back_translation_ok=None
    )
    assert outcome.abstain is False
    assert outcome.review_recommended is True


def test_score_is_clamped_to_unit_interval() -> None:
    outcome = compute_confidence(
        retrieval_margin=1.0, mean_entailment=1.0, verified_ratio=1.0, back_translation_ok=True
    )
    assert 0.0 <= outcome.score <= 1.0
