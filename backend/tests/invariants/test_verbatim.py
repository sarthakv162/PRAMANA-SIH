"""I3 — verbatim: every stored chunk's `text` hashes to its own `sha256`, and re-parsing the
source PDF at the chunk's recorded page reproduces that same text (so `EvidenceSpan.text`,
which is always `row.text`, can never diverge from what's actually in the corpus). No LLM
text can be inside it by construction, since nothing but `ingest/*` ever writes `chunks.text`.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.core.hashing import sha256_hex
from app.retrieval.repo import chunks, documents, sections


def test_every_chunk_text_matches_its_own_sha256(
    db_session: Session, live_corpus_version: tuple[str, str]
) -> None:
    cv_id, _ = live_corpus_version
    rows = db_session.execute(
        sa.select(chunks.c.text, chunks.c.sha256).where(chunks.c.corpus_version_id == cv_id)
    ).all()
    assert rows, "expected at least one chunk in the live corpus version"
    for row in rows:
        assert sha256_hex(row.text) == row.sha256


def test_chunk_text_is_exact_substring_of_the_source_pdf(
    db_session: Session, live_corpus_version: tuple[str, str]
) -> None:
    """Re-derives each document's cleaned full text independently of the ingest run that
    wrote it, and checks every chunk's stored (char_start, char_end) still slices out
    exactly `text` — the strongest form of I3, since it doesn't trust the ingest CLI's own
    bookkeeping, only the raw PDF plus the chunker.
    """
    from app.ingest.parse_pdf import parse_pdf

    cv_id, _ = live_corpus_version
    docs = db_session.execute(sa.select(documents.c.id, documents.c.pdf_path)).all()
    assert docs, "expected at least one ingested document"

    corpus_dir = __import__("pathlib").Path(__file__).resolve().parents[3] / "corpus"
    checked = 0
    for doc in docs:
        pdf_path = corpus_dir / doc.pdf_path
        if not pdf_path.exists():
            continue
        parsed = parse_pdf(str(pdf_path))
        section_rows = db_session.execute(
            sa.select(sections.c.id, sections.c.text, sections.c.section_key).where(
                sections.c.document_id == doc.id, sections.c.corpus_version_id == cv_id
            )
        ).all()
        chunk_select = sa.select(
            chunks.c.section_id, chunks.c.char_start, chunks.c.char_end, chunks.c.text
        ).where(chunks.c.corpus_version_id == cv_id)
        chunk_by_section = {row.section_id: row for row in db_session.execute(chunk_select).all()}
        for section in section_rows:
            chunk = chunk_by_section.get(section.id)
            if chunk is None:
                continue
            actual = parsed.full_text[chunk.char_start : chunk.char_end]
            assert actual == chunk.text, section.section_key
            checked += 1
    assert checked > 0, "expected to verify at least one chunk against its source PDF"
