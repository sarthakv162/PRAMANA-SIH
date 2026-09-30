"""Unit tests for intake/pii.py — invariant I4 depends on this catching real PII shapes."""

from __future__ import annotations

from app.intake.pii import _VERHOEFF_D, _VERHOEFF_P, scrub_pii

_VERHOEFF_INV = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]


def _verhoeff_checksum_digit(number_without_check: str) -> str:
    """Computes the trailing check digit so a synthetic 12-digit Aadhaar-shaped test number
    actually passes the Verhoeff validation `scrub_pii` performs — a random 12-digit string
    almost certainly wouldn't, and the scrubber must not fire on things that merely look
    like an Aadhaar number. The check digit occupies position 0 in the validation loop, so
    generation runs the same recurrence over the *other* digits (reversed, starting at
    position 1) and then inverts the result.
    """
    c = 0
    for i, digit in enumerate(reversed(number_without_check), start=1):
        c = _VERHOEFF_D[c][_VERHOEFF_P[i % 8][int(digit)]]
    return str(_VERHOEFF_INV[c])


def test_scrubs_valid_aadhaar() -> None:
    check = _verhoeff_checksum_digit("234567890123"[:-1])
    aadhaar = "23456789012" + check
    result = scrub_pii(f"my aadhaar is {aadhaar[:4]} {aadhaar[4:8]} {aadhaar[8:]}")
    assert "[AADHAAR]" in result.scrubbed_text
    assert aadhaar[:4] not in result.scrubbed_text


def test_does_not_scrub_a_bare_12_digit_number_that_fails_verhoeff() -> None:
    result = scrub_pii("case number 234567890123 is pending")
    assert "234567890123" in result.scrubbed_text
    assert "AADHAAR" not in result.found


def test_scrubs_pan_email_phone() -> None:
    result = scrub_pii("PAN ABCDE1234F, email a@b.com, phone 9876543210")
    assert result.scrubbed_text == "PAN [PAN], email [EMAIL], phone [PHONE]"
    assert set(result.found) == {"PAN", "EMAIL", "PHONE"}


def test_scrubs_gstin_before_pan_pattern_inside_it() -> None:
    result = scrub_pii("GSTIN 29ABCDE1234F1Z5 on the invoice")
    assert "[GSTIN]" in result.scrubbed_text
    assert "ABCDE1234F" not in result.scrubbed_text


def test_no_pii_passes_through_unchanged() -> None:
    result = scrub_pii("Can traditional knowledge be patented in India?")
    assert result.scrubbed_text == "Can traditional knowledge be patented in India?"
    assert result.found == []
