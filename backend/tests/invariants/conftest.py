"""DB-backed invariant tests (I1, I3, §11) need a Postgres with an ingested, live corpus
version — `make ingest && make promote V=...` (or a CI job that does the same) before
`make test` reaches this package. They skip cleanly rather than fail when that hasn't
happened, since a fresh checkout has no corpus yet.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.retrieval import repo


@pytest.fixture
def db_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def live_corpus_version(db_session: Session) -> tuple[str, str]:
    try:
        version = repo.live_corpus_version(db_session)
    except OperationalError:
        pytest.skip("database not reachable — start it with `make up` first")
    if version is None:
        pytest.skip("no live corpus_version — run `make ingest && make promote V=...` first")
    return version
