"""PII scrubbing (§6.3, invariant I4): replace PII with typed placeholders before anything
touches a log line or a DB row. **Never call `sha256_hex`/persist/log on the raw query —
always scrub first.**

Regex + checksum only (Aadhaar's Verhoeff check digit, PAN's fixed alphanumeric shape, phone,
email, GSTIN). Presidio (NER-based name/org scrubbing) is deliberately not wired in here: it
needs a spaCy model download this environment doesn't have staged, and the plan lists it as
an enhancement over the regex/checksum layer, not a replacement for it (§6.3). Structured
identifiers — the ones that are unambiguous and expensive to leak — are covered for real.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field

# --- Verhoeff checksum (used by Aadhaar) ---
_VERHOEFF_D = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
    [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
    [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]
_VERHOEFF_P = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
    [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
    [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]


def _verhoeff_valid(number: str) -> bool:
    check = 0
    for i, digit in enumerate(reversed(number)):
        if not digit.isdigit():
            return False
        check = _VERHOEFF_D[check][_VERHOEFF_P[i % 8][int(digit)]]
    return check == 0


_AADHAAR_RE = re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b")
_PAN_RE = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")
_GSTIN_RE = re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][A-Z\d]Z[A-Z\d]\b")
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?91[-\s]?)?[6-9]\d{9}(?!\d)")


@dataclass
class ScrubResult:
    scrubbed_text: str
    found: list[str] = field(default_factory=list)  # placeholder kinds found, for a unit test


def _replace_aadhaar(match: re.Match[str]) -> str:
    digits = re.sub(r"\s", "", match.group())
    return "[AADHAAR]" if len(digits) == 12 and _verhoeff_valid(digits) else match.group()


def scrub_pii(text: str) -> ScrubResult:
    """Replace PII with typed placeholders. Order matters: GSTIN before PAN (GSTIN embeds a
    PAN-shaped substring), Aadhaar before phone (a 12-digit run could otherwise partially
    match a phone pattern).
    """
    found: list[str] = []

    def _mark(kind: str, replacement: str) -> Callable[[re.Match[str]], str]:
        def _sub(_m: re.Match[str]) -> str:
            found.append(kind)
            return replacement

        return _sub

    result = text
    before = result
    result = _AADHAAR_RE.sub(_replace_aadhaar, result)
    if result != before:
        found.append("AADHAAR")
    result = _GSTIN_RE.sub(_mark("GSTIN", "[GSTIN]"), result)
    result = _PAN_RE.sub(_mark("PAN", "[PAN]"), result)
    result = _EMAIL_RE.sub(_mark("EMAIL", "[EMAIL]"), result)
    result = _PHONE_RE.sub(_mark("PHONE", "[PHONE]"), result)

    return ScrubResult(scrubbed_text=result, found=found)
