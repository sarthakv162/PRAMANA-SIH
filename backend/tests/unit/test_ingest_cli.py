from __future__ import annotations

from app.ingest.cli import _needs_ocr_review
from app.ingest.parse_pdf import Page


def _page(text: str, density: float) -> Page:
    return Page(index=0, printed_number=1, raw_text=text, text=text, density=density)


def test_ocr_review_flags_sparse_pages_but_not_whitespace_heavy_legal_text() -> None:
    assert _needs_ocr_review(_page("short fragment", density=1.0))
    assert not _needs_ocr_review(_page("legal provision " * 12, density=1.0))
    assert not _needs_ocr_review(_page("short text", density=4.0))
    assert not _needs_ocr_review(_page("<<previous   next>>", density=0.1))
    assert _needs_ocr_review(_page("", density=0.0))
