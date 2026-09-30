"""Unit tests for verification/guards.py (§6.7, §11 "guards (numbers/dates/negation)")."""

from __future__ import annotations

from app.verification.guards import (
    dates_ok,
    modal_strength_matches,
    negation_ok,
    normalize_numbers,
    numbers_ok,
    section_refs_ok,
)


def test_normalize_numbers_digits_and_words_agree() -> None:
    assert "30" in normalize_numbers("within thirty days")
    assert "30" in normalize_numbers("within 30 days")
    assert "100" in normalize_numbers("one hundred rupees")


def test_numbers_ok_true_when_claim_number_traceable() -> None:
    premise = "The application shall be made within thirty days of the order."
    claim = "The application must be filed within 30 days."
    assert numbers_ok(claim, premise) is True


def test_numbers_ok_false_when_claim_invents_a_number() -> None:
    premise = "The application shall be made within thirty days of the order."
    claim = "The application must be filed within 60 days."
    assert numbers_ok(claim, premise) is False


def test_dates_ok_false_when_year_not_in_premise() -> None:
    premise = "This Act may be called the Patents Act, 1970."
    claim = "The relevant Act was passed in 1999."
    assert dates_ok(claim, premise) is False


def test_section_refs_ok_false_when_claim_invents_a_section() -> None:
    premise = "No patent shall be granted under section 3."
    claim = "This is governed by section 5 of the Act."
    assert section_refs_ok(claim, premise) is False


def test_section_refs_ok_true_when_premise_names_it() -> None:
    premise = "No patent shall be granted under section 3(p) of the Act."
    claim = "Section 3(p) excludes traditional knowledge from patentability."
    assert section_refs_ok(claim, premise) is True


def test_negation_ok_false_when_claim_drops_the_premise_hedge() -> None:
    premise = "No patent shall be granted except where the Controller directs otherwise."
    claim = "A patent shall be granted in this case."
    assert negation_ok(claim, premise) is False


def test_negation_ok_true_when_claim_is_purely_descriptive() -> None:
    premise = "No patent shall be granted except where the Controller directs otherwise."
    claim = "This provision concerns the grant of patents."
    assert negation_ok(claim, premise) is True


def test_modal_strength_mismatch_shall_vs_may() -> None:
    premise = "The Controller may extend the period on request."
    claim = "The Controller shall extend the period on request."
    assert modal_strength_matches(claim, premise) is False


def test_modal_strength_match() -> None:
    premise = "The Controller may extend the period on request."
    claim = "The Controller may extend the period."
    assert modal_strength_matches(claim, premise) is True
