"""I1 — no cross-jurisdiction leakage: a request scoped to one jurisdiction never gets a
chunk from the other, and only `retrieval/repo.py` is allowed to query `chunks` at all (so
this can't be re-broken by some other module building its own SQL against it later).
"""

from __future__ import annotations

import ast
from datetime import date
from pathlib import Path

from sqlalchemy.orm import Session

from app.retrieval import repo


def test_retrievable_chunks_never_crosses_jurisdiction(
    db_session: Session, live_corpus_version: tuple[str, str]
) -> None:
    cv_id, _ = live_corpus_version
    for jurisdiction in ("IN", "INTL"):
        stmt = repo.retrievable_chunks(cv_id, [jurisdiction], date.today())
        rows = db_session.execute(stmt).all()
        assert all(row.jurisdiction == jurisdiction for row in rows)


def test_dense_and_keyword_search_respect_jurisdiction_filter(
    db_session: Session, live_corpus_version: tuple[str, str]
) -> None:
    cv_id, _ = live_corpus_version
    zero_vector = [0.0] * 1024
    for jurisdiction in ("IN", "INTL"):
        dense_rows = repo.dense_search(
            db_session, cv_id, [jurisdiction], date.today(), zero_vector, top_n=50
        )
        assert all(row.jurisdiction == jurisdiction for row, _ in dense_rows)
        kw_rows = repo.keyword_search(
            db_session, cv_id, [jurisdiction], date.today(), "patent", top_n=50
        )
        assert all(row.jurisdiction == jurisdiction for row, _ in kw_rows)


APP_ROOT = Path(__file__).resolve().parents[2] / "app"
ALLOWED_MODULES = {"retrieval/repo.py"}
# The jurisdiction/as-of gate is a retrieval-time (query-serving) concern; ingest writes
# `chunks` directly (as `ingest_rw`, under the immutability trigger, §6.1) and is exempt.
EXEMPT_PREFIXES = ("ingest/",)


def _references_chunks_table(source: str) -> bool:
    """True if the module's AST contains an identifier literally named `chunks` used as a
    SQLAlchemy table (`chunks.c...`, `sa.select(chunks)`, `insert(chunks)`, …). Cheap and
    conservative — false positives (e.g. a local variable also called `chunks`) just mean
    an extra module to eyeball, not a missed real violation.
    """
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == "chunks":
            return True
    return False


def test_only_repo_module_references_the_chunks_table() -> None:
    offenders = []
    for path in APP_ROOT.rglob("*.py"):
        rel = path.relative_to(APP_ROOT).as_posix()
        if rel in ALLOWED_MODULES or rel.startswith(EXEMPT_PREFIXES):
            continue
        source = path.read_text()
        if _references_chunks_table(source):
            offenders.append(rel)
    assert not offenders, (
        f"only retrieval/repo.py may reference the `chunks` table (CLAUDE.md); "
        f"found references in: {offenders}"
    )
