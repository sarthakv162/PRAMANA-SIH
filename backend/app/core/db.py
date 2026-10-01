"""SQLAlchemy 2 engine/session plumbing.

Tables are managed entirely via Alembic raw-SQL migrations (see alembic/versions/) rather
than declarative ORM model classes — the schema is DDL-first because the immutability
trigger, HNSW/GIN indexes, and role grants in §6.1 are easier to reason about as SQL than
to reverse-engineer from an ORM mapping. Modules that need typed row access should use
`sqlalchemy.text()` against the session returned by `get_session()`, or add narrow
`sa.Table` reflections where useful (e.g. retrieval/repo.py).
"""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    """Reserved for any future ORM-mapped models. No tables are mapped here yet."""


_settings = get_settings()
engine = create_engine(_settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

# Corpus writes and promotion use a separate, narrowly-scoped database role. API request
# handling never receives the ingest credentials.
ingest_engine = create_engine(
    _settings.ingest_database_url or _settings.database_url,
    pool_pre_ping=True,
    future=True,
)
IngestSessionLocal = sessionmaker(
    bind=ingest_engine, autoflush=False, autocommit=False, future=True
)


@contextmanager
def session_scope() -> Iterator[Session]:
    """`with session_scope() as session:` for plain (non-FastAPI) call sites — CLI scripts,
    background jobs, tests.
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_session() -> Iterator[Session]:
    """FastAPI dependency: `Depends(get_session)`. A plain generator, not `@contextmanager` —
    FastAPI's dependency system specifically needs `inspect.isgeneratorfunction()` to be true
    to run this as a yield-dependency; wrapping it in `@contextmanager` makes calling it
    return a context-manager *object* instead, which FastAPI would then inject unentered.
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
