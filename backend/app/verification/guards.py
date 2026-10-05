"""Regex guards (§6.7) — the deterministic half of verification, alongside NLI. Each guard
answers one narrow question about a (premise, claim) pair; `verify.py` combines them. Pure
regex/string logic, no model, so these are exhaustively unit-testable and never "hallucinate"
a pass.
"""

from __future__ import annotations

import re

_ONES = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
}
_TENS = {
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}
_MULTIPLIERS = {"hundred": 100, "thousand": 1000, "lakh": 100_000, "crore": 10_000_000}
_ORDINAL_WORDS = {
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
    "fifth": 5,
    "sixth": 6,
    "seventh": 7,
    "eighth": 8,
    "ninth": 9,
    "tenth": 10,
    "twentieth": 20,
    "thirtieth": 30,
}

_ALL_NUMBER_WORDS = sorted({*_ONES, *_TENS, *_MULTIPLIERS, *_ORDINAL_WORDS}, key=len, reverse=True)
_CONTINUATION_WORDS = sorted({*_ONES, *_TENS, *_MULTIPLIERS}, key=len, reverse=True)
_WORD_NUMBER_RE = re.compile(
    r"\b(?:" + "|".join(_ALL_NUMBER_WORDS) + r")(?:[\s-](?:" + "|".join(_CONTINUATION_WORDS) + r"))*\b",
    re.IGNORECASE,
)

_DIGIT_NUMBER_RE = re.compile(r"\b\d[\d,]*(?:\.\d+)?\s*%?\b|₹\s?\d[\d,]*|(?:Rs\.?)\s?\d[\d,]*")
_ORDINAL_DIGIT_RE = re.compile(r"\b\d+(?:st|nd|rd|th)\b", re.IGNORECASE)
_YEAR_RE = re.compile(r"\b(1[89]\d{2}|20\d{2})\b")
_SECTION_REF_RE = re.compile(
    r"(?<!\w)(?:sections?|rules?|clauses?|sub[\s-]?sections?|secs?\.?|s\.?|§)\s*"
    r"(\d+[A-Za-z]*(?:\([a-zA-Z0-9]+\))*)",
    re.IGNORECASE,
)

_NEGATION_CUES = re.compile(
    r"\b(shall not|no .{0,30} shall|except|unless|provided that|not be|excluding)\b",
    re.IGNORECASE,
)
_MODAL_SHALL = re.compile(r"\bshall\b", re.IGNORECASE)
_MODAL_MAY = re.compile(r"\bmay\b", re.IGNORECASE)


def _word_to_number(phrase: str) -> int | None:
    tokens = re.split(r"[\s-]+", phrase.lower())
    total = 0
    current = 0
    matched_any = False
    for tok in tokens:
        if tok in _ONES:
            current += _ONES[tok]
            matched_any = True
        elif tok in _TENS:
            current += _TENS[tok]
            matched_any = True
        elif tok in _ORDINAL_WORDS:
            current += _ORDINAL_WORDS[tok]
            matched_any = True
        elif tok in _MULTIPLIERS:
            current = (current or 1) * _MULTIPLIERS[tok]
            matched_any = True
        else:
            return None
    total += current
    return total if matched_any else None


def normalize_numbers(text: str) -> set[str]:
    """Extract every number mentioned in `text`, normalised to a comparable digit string.
    Percent signs and currency markers are preserved on the digit form so "30%" and "thirty"
    don't collide with a plain "30" that means something different.
    """
    found: set[str] = set()

    for match in _DIGIT_NUMBER_RE.finditer(text):
        raw = match.group().strip()
        digits = re.sub(r"[,\s]", "", raw)
        found.add(digits)

    for match in _ORDINAL_DIGIT_RE.finditer(text):
        found.add(re.sub(r"(?:st|nd|rd|th)", "", match.group(), flags=re.IGNORECASE))

    for match in _WORD_NUMBER_RE.finditer(text):
        value = _word_to_number(match.group())
        if value is not None:
            found.add(str(value))

    return found


def _cited_titles_in_claim(claim_text: str, citation_metadata: str) -> str:
    """Allow a source year only when the claim names that cited document title."""
    normalized_claim = claim_text.casefold()
    titles: list[str] = []
    for label in citation_metadata.splitlines():
        title = label.split(" — ", maxsplit=1)[0].strip()
        without_article = re.sub(r"^the\s+", "", title, flags=re.IGNORECASE)
        if _YEAR_RE.search(title) and any(
            variant and variant.casefold() in normalized_claim for variant in (title, without_article)
        ):
            titles.append(title)
    return " ".join(titles)


def numbers_ok(claim_text: str, premise: str, citation_metadata: str = "") -> bool:
    """Every substantive number must be traceable to the premise (§6.7 Numbers guard).

    Section/rule identifiers are checked separately by `section_refs_ok`; validated source
    labels may also substantiate an Act-title year (e.g. "Patents Act, 1970"). Neither source
    labels nor locator numbers are added to the NLI premise.
    """
    cited_titles = _cited_titles_in_claim(claim_text, citation_metadata)
    claim_numbers = normalize_numbers(_SECTION_REF_RE.sub(" ", claim_text))
    if not claim_numbers:
        return True
    source = f"{premise} {cited_titles}"
    premise_numbers = normalize_numbers(_SECTION_REF_RE.sub(" ", source))
    return claim_numbers.issubset(premise_numbers)


def dates_ok(claim_text: str, premise: str, citation_metadata: str = "") -> bool:
    """Every year in the claim must appear in the premise (§6.7 Dates/years guard)."""
    claim_years = set(_YEAR_RE.findall(claim_text))
    if not claim_years:
        return True
    cited_titles = _cited_titles_in_claim(claim_text, citation_metadata)
    premise_years = set(_YEAR_RE.findall(f"{premise} {cited_titles}"))
    return claim_years.issubset(premise_years)


def section_refs_ok(claim_text: str, premise: str, citation_refs: set[str] | None = None) -> bool:
    """Every section/rule named by a claim must occur in cited text or its locator.

    Statutory excerpts often start at a clause and omit the parent section heading. In that
    case, the server-validated section key attached to the cited span is valid locator
    evidence for the section reference; it does not add any substantive text to the NLI
    premise.
    """

    def _normalize(ref: str) -> str:
        return re.sub(r"\s+", " ", ref.strip().lower())

    def _canonical(match: re.Match[str]) -> str:
        return f"section {match.group(1).lower()}"

    claim_refs = {_normalize(_canonical(m)) for m in _SECTION_REF_RE.finditer(claim_text)}
    if not claim_refs:
        return True
    premise_refs = {_normalize(_canonical(m)) for m in _SECTION_REF_RE.finditer(premise)}
    premise_refs.update(_normalize(ref) for ref in (citation_refs or set()))
    return claim_refs.issubset(premise_refs)


def negation_ok(claim_text: str, premise: str) -> bool:
    """If the premise is conditional/negated (a proviso, an exception, a "shall not") but the
    claim states an unconditional positive, that's a modality mismatch worth downgrading
    (§6.7 Negation/modality guard). This can't fully verify correctness — it's a coarse
    tripwire, not a logic checker — so it only fires on the clearest mismatch: the premise
    hedges and the claim asserts a bare, unqualified obligation with none of that hedging.
    """
    premise_hedged = bool(_NEGATION_CUES.search(premise))
    if not premise_hedged:
        return True
    claim_hedged = bool(_NEGATION_CUES.search(claim_text))
    if claim_hedged:
        return True
    # premise hedges, claim doesn't — only a problem if the claim also asserts something
    # with modal force (shall/may); a purely descriptive claim isn't affected.
    return not (_MODAL_SHALL.search(claim_text) or _MODAL_MAY.search(claim_text))


def modal_strength_matches(claim_text: str, premise: str) -> bool:
    """ "shall" (mandatory) vs "may" (discretionary) mismatch between claim and premise."""
    premise_shall = bool(_MODAL_SHALL.search(premise))
    premise_may = bool(_MODAL_MAY.search(premise))
    claim_shall = bool(_MODAL_SHALL.search(claim_text))
    claim_may = bool(_MODAL_MAY.search(claim_text))
    if claim_shall and premise_may and not premise_shall:
        return False
    if claim_may and premise_shall and not premise_may:
        return False
    return True
