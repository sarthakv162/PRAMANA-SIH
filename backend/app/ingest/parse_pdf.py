"""PDF → cleaned, page-offset-tracked text (§6.2 steps 2–4).

Indian statute PDFs from India Code / IP India follow a consistent layout: a bare page
number at the top of the body text, footnotes (amendment history) below a horizontal rule
near the bottom, and inline amendment markers like `4[(b) ...]` (clause substituted by
amendment #4, whose citation is in the footnote) or `1* * * *` (a clause omitted by
amendment #1, replaced by a run of asterisks). `clean_page_text` strips all of these —
page number, footnote block, and amendment markers — on a **per-page** basis, so
`page_offsets` computed after cleaning stay accurate. Amendment brackets that happen to
open on one page and close on the next are a known gap (the stray bracket character is
left in the text); §8 already expects manual QA of Tier-A section boundaries.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import pymupdf

# A footnote block starts after a line of many spaces/tabs acting as a horizontal rule —
# there is no drawn line in the extracted text, just the whitespace where it would be.
_FOOTNOTE_SEPARATOR = re.compile(r"\n[ \t]{15,}\n")
_LEADING_PAGE_NUMBER = re.compile(r"^\s*\d{1,4}\s*\n")
# "4[(b) text]" -> "(b) text" — digit-prefixed brackets mark amendment-inserted/substituted
# text; the digit is a footnote reference, not part of the clause. Brackets *without* a
# digit prefix (e.g. "[Omitted.]") are left alone — those are the Act's own convention for
# marking a repealed section, not a footnote artifact.
_AMENDMENT_BRACKET = re.compile(r"\d+\[([^\[\]]*)\]")
# "1* * * *" / "3***" — an omitted clause or omitted words, replaced by asterisks.
_OMITTED_PLACEHOLDER = re.compile(r"\d?(?:\*\s*){2,}")


@dataclass
class Page:
    index: int  # 0-based, matches PyMuPDF page index
    printed_number: int  # 1-based page as a human would cite it
    raw_text: str
    text: str  # cleaned (footnote/page-number stripped), single-spaced
    density: float  # chars per page-area unit; low density ⇒ likely a scanned/image page


@dataclass
class ParsedDocument:
    pages: list[Page]
    full_text: str  # all pages' cleaned text, joined with a single space
    page_offsets: list[int]  # page_offsets[i] = start char of pages[i].text in full_text


def clean_page_text(raw_text: str) -> str:
    match = _FOOTNOTE_SEPARATOR.search(raw_text)
    body = raw_text[: match.start()] if match else raw_text
    body = _LEADING_PAGE_NUMBER.sub("", body)
    body = _AMENDMENT_BRACKET.sub(r"\1", body)
    body = _OMITTED_PLACEHOLDER.sub(" ", body)
    return " ".join(body.split())


# Below this, a page is almost certainly a scan/image rather than text-native (§6.2 step 2).
OCR_DENSITY_FLOOR = 3.0


def parse_pdf(pdf_path: str) -> ParsedDocument:
    # pymupdf ships no type stubs, so every call into it is "untyped" as far as mypy is
    # concerned — the ignores below are about that gap, not about our own code.
    doc = pymupdf.open(pdf_path)  # type: ignore[no-untyped-call]
    pages: list[Page] = []
    try:
        for i in range(doc.page_count):
            page = doc[i]
            raw_text = page.get_text("text")  # type: ignore[no-untyped-call]
            area = page.rect.width * page.rect.height
            density = (len(raw_text) / area) * 1000 if area else 0.0
            pages.append(
                Page(
                    index=i,
                    printed_number=i + 1,
                    raw_text=raw_text,
                    text=clean_page_text(raw_text),
                    density=density,
                )
            )
    finally:
        doc.close()  # type: ignore[no-untyped-call]

    full_text_parts: list[str] = []
    page_offsets: list[int] = []
    cursor = 0
    for pg in pages:
        page_offsets.append(cursor)
        full_text_parts.append(pg.text)
        cursor += len(pg.text) + 1  # +1 for the joining space
    full_text = " ".join(full_text_parts)

    return ParsedDocument(pages=pages, full_text=full_text, page_offsets=page_offsets)


def page_for_offset(parsed: ParsedDocument, char_offset: int) -> int:
    """Return the printed page number containing `char_offset` in `parsed.full_text`."""
    page_idx = 0
    for i, start in enumerate(parsed.page_offsets):
        if start <= char_offset:
            page_idx = i
        else:
            break
    return parsed.pages[page_idx].printed_number
