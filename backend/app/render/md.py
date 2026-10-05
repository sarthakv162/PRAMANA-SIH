"""Markdown dossier renderer (§6.11). The plainest of the three formats — useful as a diff-
able/gitable export and as the reference for what content the PDF/DOCX renderers must also
carry.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.render.dossier import DISCLAIMER, DossierItem


def render_md(items: list[DossierItem], language: str) -> bytes:
    lines = [
        "# PRAMANA compliance dossier",
        "",
        f"Generated: {datetime.now(UTC).isoformat()}",
        "Language: preserved from saved results and original source text; no export translation.",
        "",
        "---",
        "",
    ]
    for i, item in enumerate(items, start=1):
        lines.append(f"## {i}. {item.title}")
        lines.append("")
        if item.kind == "missing":
            lines.append(f"*{item.note}*")
            lines.append("")
            continue
        meta = []
        if item.corpus_version:
            meta.append(f"corpus version `{item.corpus_version}`")
        if item.as_of:
            meta.append(f"as of `{item.as_of}`")
        if item.jurisdiction:
            meta.append(f"jurisdiction `{item.jurisdiction}`")
        if meta:
            lines.append(" · ".join(meta))
            lines.append("")
        for line in item.summary_lines:
            lines.append(line)
        lines.append("")
        if item.quotes:
            lines.append("**Statutory text cited:**")
            lines.append("")
            for quote in item.quotes:
                page = f", p.{quote.page}" if quote.page else ""
                lines.append(f"> **{quote.citation_label}**{page}")
                lines.append(">")
                for text_line in quote.text.splitlines() or [""]:
                    lines.append(f"> {text_line}")
                lines.append("")
        lines.append(f"Request: `{item.request_id}` · Receipt: `{item.receipt_id}` · Entry hash: `{item.entry_hash}`")
        lines.append("")
        lines.append("---")
        lines.append("")
    lines.append(f"*{DISCLAIMER}*")
    return ("\n".join(lines) + "\n").encode("utf-8")
