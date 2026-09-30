"""EvidenceSpan — the only place statutory text appears. See §5.2.

Design rule (docs/IMPLEMENTATION_PLAN.md §2): the LLM never writes quotes. `text` is always
materialised by the server from the DB, verbatim, at [char_start:char_end).
"""

from datetime import date
from typing import Literal

from pydantic import Field

from app.schemas.base import ContractModel
from app.schemas.enums import DocType


class Highlight(ContractModel):
    page: int
    page_width: float
    page_height: float
    rects: list[list[float]] = Field(
        description="Each rect is [x0, y0, x1, y1] in PDF points, origin top-left (PyMuPDF)."
    )


class EvidenceSpan(ContractModel):
    id: str
    doc_id: str
    doc_title: str
    doc_type: DocType
    jurisdiction: Literal["IN", "INTL"]
    citation_label: str
    section_key: str
    section_path: list[str]
    page: int
    page_end: int
    char_start: int
    char_end: int
    text: str
    sha256: str
    effective_from: date
    effective_to: date | None = None
    corpus_version: str
    source_url: str
    pdf_url: str
    highlights: list[Highlight] = Field(default_factory=list)
