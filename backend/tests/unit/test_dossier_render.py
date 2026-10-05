"""Unit tests for render/dossier.py + pdf.py/docx.py/md.py (§6.11) — pure functions over a
synthetic `StoredResult`, no DB needed. The one invariant that matters here is the same one
that matters for the live API response: evidence `text` reaches every format byte-for-byte,
never reformatted or truncated (§2).
"""

from __future__ import annotations

from app.audit.receipts import StoredResult
from app.render.docx import render_docx
from app.render.dossier import build_dossier_item, missing_item
from app.render.md import render_md
from app.render.pdf import render_pdf


def test_multilingual_export_preserves_unicode_or_rejects_unsupported_pdf_font():
    import io
    import zipfile

    import pytest

    from app.render.dossier import DossierItem

    text = "आयुर्वेद का स्रोत पाठ"
    item = DossierItem(
        request_id="test",
        receipt_id="test",
        entry_hash="hash",
        kind="answer",
        title="Answer",
        corpus_version=None,
        as_of=None,
        jurisdiction=None,
        summary_lines=[text],
    )
    assert text in render_md([item], "auto").decode()
    document = render_docx([item], "auto")
    with zipfile.ZipFile(io.BytesIO(document)) as archive:
        assert text in archive.read("word/document.xml").decode()
    with pytest.raises(UnicodeEncodeError):
        render_pdf([item], "auto")


_VERBATIM_TEXT = (
    "(p) an invention which, in effect, is traditional knowledge or which is an "
    'aggregation or duplication of known properties — including "quoted" & <tagged> text.'
)

_ANSWER_PAYLOAD = {
    "type": "answer",
    "request_id": "req-1",
    "corpus_version": "2026.09.28-a",
    "as_of": "2026-09-30",
    "jurisdiction": "IN",
    "sections": [
        {
            "jurisdiction": "IN",
            "heading": "India",
            "claims": [{"text": "Classical TK is excluded from patenting.", "status": "verified"}],
            "gaps": [],
        }
    ],
    "evidence": {
        "ev_1": {
            "citation_label": "The Patents Act, 1970 — s.3(p)",
            "page": 10,
            "text": _VERBATIM_TEXT,
        }
    },
    "dropped_claims": 0,
    "confidence": {"level": "high", "score": 0.9},
}

_REFUSAL_PAYLOAD = {
    "type": "refusal",
    "reason": "no_evidence",
    "message": "The indexed documents don't cover this.",
    "nearest_sources": [{"citation_label": "The Patents Act, 1970 — s.47", "page": 28, "text": _VERBATIM_TEXT}],
}


def _stored(payload: dict[str, object]) -> StoredResult:
    return StoredResult(
        request_id="req-1",
        receipt_id="rcp_1",
        entry_hash="deadbeef",
        result=payload,
        request_payload=None,
    )


def test_answer_item_carries_verbatim_evidence_text() -> None:
    item = build_dossier_item(_stored(_ANSWER_PAYLOAD))
    assert item.kind == "answer"
    assert len(item.quotes) == 1
    assert item.quotes[0].text == _VERBATIM_TEXT
    assert any("verified" in line for line in item.summary_lines)


def test_refusal_item_uses_nearest_sources_as_quotes() -> None:
    item = build_dossier_item(_stored(_REFUSAL_PAYLOAD))
    assert item.kind == "refusal"
    assert item.quotes[0].text == _VERBATIM_TEXT
    assert "no_evidence" in item.summary_lines[0]


def test_missing_item_has_no_quotes_and_a_note() -> None:
    item = missing_item("req-ghost")
    assert item.kind == "missing"
    assert item.note is not None
    assert "req-ghost" in item.note


def _all_items() -> list[object]:
    return [
        build_dossier_item(_stored(_ANSWER_PAYLOAD)),
        build_dossier_item(_stored(_REFUSAL_PAYLOAD)),
        missing_item("req-ghost"),
    ]


def test_markdown_renderer_preserves_verbatim_text_and_disclaimer() -> None:
    out = render_md(_all_items(), "en").decode("utf-8")
    assert _VERBATIM_TEXT in out
    assert "Informational, not legal advice." in out
    assert "req-ghost" in out


def test_docx_renderer_preserves_verbatim_text() -> None:
    import io

    from docx import Document

    out = render_docx(_all_items(), "en")
    doc = Document(io.BytesIO(out))
    full_text = "\n".join(p.text for p in doc.paragraphs)
    assert _VERBATIM_TEXT in full_text
    assert "Informational, not legal advice." in full_text


def test_pdf_renderer_preserves_verbatim_text_through_xml_escaping() -> None:
    import fitz  # pymupdf — already a dependency, used here only to read the PDF back

    out = render_pdf(_all_items(), "en")
    assert out.startswith(b"%PDF")

    doc = fitz.open(stream=out, filetype="pdf")
    full_text = "".join(page.get_text() for page in doc)

    def _normalize(text: str) -> str:
        return " ".join(text.split())  # PDF layout re-flows lines; collapse to compare content

    # Quotes/angle-brackets/ampersand must survive reportlab's HTML-like markup escaping and
    # come back out as the original characters, not as literal "&amp;"/"&lt;" entities.
    assert _normalize(_VERBATIM_TEXT) in _normalize(full_text)
    assert "Informational, not legal advice." in full_text
