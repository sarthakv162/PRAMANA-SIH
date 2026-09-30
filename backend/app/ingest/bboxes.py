"""Locate a chunk's text on its PDF page(s) as highlight rectangles (§6.2 step 4).

Uses PyMuPDF's own `page.search_for`, which matches a text needle against the page's word
layout (tolerant of the line-wrapping our chunk text no longer has, since it was already
whitespace-normalised in `parse_pdf.clean_page_text`) rather than re-implementing word-box
sequence alignment by hand. A chunk that spans a page break, or whose exact text can't be
found (rare — usually a case the amendment-bracket/asterisk cleanup didn't fully catch),
comes back with no rects; the caller logs it in the ingest report and the frontend falls
back to text-only display (§7.3 Source Drawer), which is an explicit, documented fallback.
"""

from __future__ import annotations

import pymupdf

MAX_NEEDLE_CHARS = 400  # a full search_for over a very long chunk is slow and unnecessary —
# matching its first sentence is enough to place the highlight.


def find_highlights(doc: pymupdf.Document, page_number: int, text: str) -> list[dict[str, object]]:
    """`page_number` is 1-based (printed page). Returns a list of highlight dicts matching
    `schemas.evidence.Highlight` (empty if the text couldn't be located).
    """
    if page_number < 1 or page_number > doc.page_count:
        return []
    page = doc[page_number - 1]
    needle = text[:MAX_NEEDLE_CHARS].strip()
    if not needle:
        return []

    quads = page.search_for(needle, quads=True)
    if not quads:
        # Long clauses sometimes fail a whole-needle search because a mid-sentence
        # amendment bracket was stripped on our side but not on the page's; retry on just
        # the opening words, which is usually enough to anchor the highlight.
        first_line = needle.split(". ")[0][:120]
        quads = page.search_for(first_line, quads=True) if first_line else []
    if not quads:
        return []

    rect = page.rect
    rects = [[q.rect.x0, q.rect.y0, q.rect.x1, q.rect.y1] for q in quads]
    return [
        {
            "page": page_number,
            "page_width": rect.width,
            "page_height": rect.height,
            "rects": rects,
        }
    ]
