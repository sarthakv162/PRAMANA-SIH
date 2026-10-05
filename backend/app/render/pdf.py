"""PDF dossier renderer (§6.11) via ReportLab. Verbatim evidence text is XML-escaped before
being handed to ReportLab's Paragraph markup (which is HTML-like) — that's encoding for the
renderer, not reformatting the content (§2's "never reformat" is about not altering the
string; every character the corpus stored still reaches the page).
"""

from __future__ import annotations

import io
from datetime import UTC, datetime
from xml.sax.saxutils import escape

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Flowable, Paragraph, SimpleDocTemplate, Spacer

from app.render.dossier import DISCLAIMER, DossierItem

_STYLES = getSampleStyleSheet()
_QUOTE_STYLE = ParagraphStyle(
    "Quote",
    parent=_STYLES["Code"],
    leftIndent=12,
    borderColor=HexColor("#888888"),
    borderWidth=0.5,
    borderPadding=6,
    backColor=HexColor("#f4f4f4"),
)
_META_STYLE = ParagraphStyle("Meta", parent=_STYLES["Normal"], textColor=HexColor("#555555"), fontSize=8)


def _p(text: str, style_name: str = "Normal") -> Paragraph:
    return Paragraph(escape(text).replace("\n", "<br/>"), _STYLES[style_name])


def render_pdf(items: list[DossierItem], language: str) -> bytes:
    # Built-in PDF fonts cover Windows-1252, not Indic scripts. Fail clearly rather than
    # producing a download with missing glyphs; DOCX/Markdown preserve Unicode text.
    for item in items:
        for text in [
            item.title,
            item.note or "",
            *item.summary_lines,
            *[q.text for q in item.quotes],
            *[q.citation_label for q in item.quotes],
        ]:
            text.encode("cp1252")
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
    )
    story: list[Flowable] = [
        Paragraph("PRAMANA compliance dossier", _STYLES["Title"]),
        Paragraph(
            escape(f"Generated: {datetime.now(UTC).isoformat()} · Saved and source text preserved"),
            _META_STYLE,
        ),
        Spacer(1, 10),
    ]

    for i, item in enumerate(items, start=1):
        story.append(Paragraph(escape(f"{i}. {item.title}"), _STYLES["Heading1"]))

        if item.kind == "missing":
            story.append(_p(item.note or ""))
            story.append(Spacer(1, 10))
            continue

        meta_bits = []
        if item.corpus_version:
            meta_bits.append(f"corpus version {item.corpus_version}")
        if item.as_of:
            meta_bits.append(f"as of {item.as_of}")
        if item.jurisdiction:
            meta_bits.append(f"jurisdiction {item.jurisdiction}")
        if meta_bits:
            story.append(Paragraph(escape(" · ".join(meta_bits)), _META_STYLE))
            story.append(Spacer(1, 4))

        for line in item.summary_lines:
            story.append(_p(line))
        story.append(Spacer(1, 6))

        for quote in item.quotes:
            page = f", p.{quote.page}" if quote.page else ""
            story.append(Paragraph(escape(f"{quote.citation_label}{page}"), _STYLES["Heading4"]))
            story.append(Paragraph(escape(quote.text).replace("\n", "<br/>"), _QUOTE_STYLE))
            story.append(Spacer(1, 6))

        story.append(
            Paragraph(
                escape(f"Request: {item.request_id} · Receipt: {item.receipt_id} · Entry hash: {item.entry_hash}"),
                _META_STYLE,
            )
        )
        story.append(Spacer(1, 14))

    story.append(Paragraph(escape(DISCLAIMER), _STYLES["Italic"]))
    doc.build(story)
    return buffer.getvalue()
