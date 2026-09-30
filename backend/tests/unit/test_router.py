"""Unit tests for orchestrator/router.py (§6.4 `route`, invariant I6)."""

from __future__ import annotations

from app.orchestrator import router


def test_legal_advice_pattern_wins_over_everything_else() -> None:
    intent, section = router.route("Should I file a patent for my formulation?")
    assert intent == "legal_advice"
    assert section is None


def test_direct_citation_fast_path() -> None:
    intent, section = router.route("What does section 3(p) of the Patents Act say?")
    assert intent == "qa"
    assert section == "patents_act_1970#s3(p)"


def test_keyword_rule_classify() -> None:
    intent, _ = router.route("How do I classify my Ayurvedic formulation?")
    assert intent == "classify"


def test_keyword_rule_patent_risk() -> None:
    intent, _ = router.route("What is the patent risk for this formulation?")
    assert intent == "patent_risk"


def test_keyword_rule_abs() -> None:
    intent, _ = router.route("Do I need NBA approval for access and benefit sharing?")
    assert intent == "abs"


def test_keyword_rule_dossier() -> None:
    intent, _ = router.route("Build a compliance dossier for my case.")
    assert intent == "dossier"
