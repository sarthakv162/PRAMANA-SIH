import uuid
from datetime import date

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import DBAPIError

from app.core.db import IngestSessionLocal
from app.retrieval import repo


def test_live_version_rejects_new_chunks(
    live_corpus_version: tuple[str, str],
) -> None:
    corpus_version_id, _ = live_corpus_version
    with IngestSessionLocal() as session:
        source = session.execute(
            sa.select(repo.chunks)
            .where(repo.chunks.c.corpus_version_id == corpus_version_id)
            .limit(1)
        ).first()
        if source is None:
            pytest.skip("live corpus has no chunks")

        statement = sa.insert(repo.chunks).values(
            id=uuid.uuid4(),
            section_id=source.section_id,
            corpus_version_id=corpus_version_id,
            jurisdiction=source.jurisdiction,
            doc_type=source.doc_type,
            effective_from=date.today(),
            effective_to=None,
            page=source.page,
            char_start=source.char_start,
            char_end=source.char_end,
            text=source.text,
            embed_text=source.embed_text,
            sha256=source.sha256,
            bboxes=source.bboxes,
            embedding=source.embedding,
            tsv=source.tsv,
        )
        with pytest.raises(DBAPIError):
            with session.begin_nested():
                session.execute(statement)

        update = (
            sa.update(repo.chunks)
            .where(repo.chunks.c.id == source.id)
            .values(char_start=source.char_start + 1)
        )
        with pytest.raises(DBAPIError):
            with session.begin_nested():
                session.execute(update)
