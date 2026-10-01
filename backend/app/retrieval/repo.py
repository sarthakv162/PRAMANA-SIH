"""The gatekeeper for the `chunks` table (docs/IMPLEMENTATION_PLAN.md §6.5, §2).

Design rule that must not be broken: **only this module may query `chunks`**. Every other
module — keyword search, dense search, graph expansion, the resolve stage — calls the
functions here rather than building its own SQL against `chunks`/`sections`. That keeps the
jurisdiction firewall (invariant I1) and as-of correctness (I2) in one place instead of
re-implemented (and possibly re-broken) at every call site.

The schema is DDL-first (see core/db.py), so tables are declared here as plain
`sqlalchemy.Table` reflections — just enough metadata to build composable `select()`
statements — rather than full ORM models.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Session

metadata = sa.MetaData()

corpus_versions = sa.Table(
    "corpus_versions",
    metadata,
    sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column("label", sa.Text),
    sa.Column("status", sa.Text),
    sa.Column("merkle_root", sa.Text),
    sa.Column("created_at", sa.DateTime(timezone=True)),
    sa.Column("notes", sa.Text),
)

documents = sa.Table(
    "documents",
    metadata,
    sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column("short_key", sa.Text),
    sa.Column("title", sa.Text),
    sa.Column("doc_type", sa.Text),
    sa.Column("jurisdiction", sa.Text),
    sa.Column("issuer", sa.Text),
    sa.Column("source_url", sa.Text),
    sa.Column("pdf_path", sa.Text),
    sa.Column("file_sha256", sa.Text),
    sa.Column("language", sa.Text),
    sa.Column("in_force_from", sa.Date),
    sa.Column("in_force_to", sa.Date),
)

sections = sa.Table(
    "sections",
    metadata,
    sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column("document_id", sa.dialects.postgresql.UUID(as_uuid=True)),
    sa.Column("corpus_version_id", sa.dialects.postgresql.UUID(as_uuid=True)),
    sa.Column("section_key", sa.Text),
    sa.Column("path", sa.dialects.postgresql.ARRAY(sa.Text)),
    sa.Column("heading", sa.Text),
    sa.Column("parent_id", sa.dialects.postgresql.UUID(as_uuid=True)),
    sa.Column("effective_from", sa.Date),
    sa.Column("effective_to", sa.Date),
    sa.Column("supersedes_id", sa.dialects.postgresql.UUID(as_uuid=True)),
    sa.Column("page_start", sa.Integer),
    sa.Column("page_end", sa.Integer),
    sa.Column("text", sa.Text),
    sa.Column("sha256", sa.Text),
)

chunks = sa.Table(
    "chunks",
    metadata,
    sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column("section_id", sa.dialects.postgresql.UUID(as_uuid=True)),
    sa.Column("corpus_version_id", sa.dialects.postgresql.UUID(as_uuid=True)),
    sa.Column("jurisdiction", sa.Text),
    sa.Column("doc_type", sa.Text),
    sa.Column("effective_from", sa.Date),
    sa.Column("effective_to", sa.Date),
    sa.Column("page", sa.Integer),
    sa.Column("char_start", sa.Integer),
    sa.Column("char_end", sa.Integer),
    sa.Column("text", sa.Text),
    sa.Column("embed_text", sa.Text),
    sa.Column("sha256", sa.Text),
    sa.Column("bboxes", sa.dialects.postgresql.JSONB),
    sa.Column("embedding", Vector(1024)),
    sa.Column("tsv", TSVECTOR),
)

edges = sa.Table(
    "edges",
    metadata,
    sa.Column("src_section_id", sa.dialects.postgresql.UUID(as_uuid=True)),
    sa.Column("dst_section_id", sa.dialects.postgresql.UUID(as_uuid=True)),
    sa.Column("kind", sa.Text),
    sa.Column("corpus_version_id", sa.dialects.postgresql.UUID(as_uuid=True)),
)


def retrievable_chunks(
    corpus_version_id: str,
    jurisdictions: list[str],
    as_of: date,
    doc_types: list[str] | None = None,
) -> sa.Select[Any]:
    """The one predicate every chunk search composes on (§6.5).

    Filters: pinned corpus_version, jurisdiction allow-list, and as-of window
    (`effective_from <= as_of < effective_to`, open-ended `effective_to` included).
    """
    stmt = sa.select(chunks).where(
        chunks.c.corpus_version_id == corpus_version_id,
        chunks.c.jurisdiction.in_(jurisdictions),
        chunks.c.effective_from <= as_of,
        sa.or_(chunks.c.effective_to.is_(None), chunks.c.effective_to > as_of),
    )
    if doc_types:
        stmt = stmt.where(chunks.c.doc_type.in_(doc_types))
    return stmt


def live_corpus_version(session: Session) -> tuple[str, str] | None:
    """Return `(id, label)` of the current live corpus version, or None if none is live."""
    row = session.execute(
        sa.select(corpus_versions.c.id, corpus_versions.c.label)
        .where(corpus_versions.c.status == "live")
        .order_by(corpus_versions.c.created_at.desc())
        .limit(1)
    ).first()
    return (str(row.id), row.label) if row else None


def corpus_version_by_label(session: Session, label: str) -> str | None:
    row = session.execute(
        sa.select(corpus_versions.c.id).where(corpus_versions.c.label == label)
    ).first()
    return str(row.id) if row else None


def fetch_chunks_by_ids(
    session: Session,
    chunk_ids: list[str],
    corpus_version_id: str,
    jurisdictions: list[str],
    as_of: date,
) -> list[sa.Row[Any]]:
    """Resolve a set of chunk IDs, but still through the jurisdiction/as-of gate.

    A chunk ID chosen by an upstream ranking stage is re-checked here rather than trusted,
    so a bug in ranking can never leak a chunk outside the request's jurisdiction/as-of window.
    """
    if not chunk_ids:
        return []
    base = retrievable_chunks(corpus_version_id, jurisdictions, as_of)
    stmt = base.where(chunks.c.id.in_(chunk_ids))
    return list(session.execute(stmt).all())


def fetch_sections_by_ids(session: Session, section_ids: list[str]) -> list[sa.Row[Any]]:
    if not section_ids:
        return []
    stmt = sa.select(sections).where(sections.c.id.in_(section_ids))
    return list(session.execute(stmt).all())


def fetch_section_by_key(
    session: Session, section_key: str, corpus_version_id: str
) -> sa.Row[Any] | None:
    stmt = sa.select(sections).where(
        sections.c.section_key == section_key,
        sections.c.corpus_version_id == corpus_version_id,
    )
    return session.execute(stmt).first()


def fetch_chunks_for_section(
    session: Session,
    section_id: str,
    corpus_version_id: str,
    jurisdictions: list[str],
    as_of: date,
) -> list[sa.Row[Any]]:
    """Fetch a section's chunks through the shared corpus/jurisdiction/as-of gate."""
    stmt = retrievable_chunks(corpus_version_id, jurisdictions, as_of)
    stmt = stmt.where(chunks.c.section_id == section_id).order_by(chunks.c.char_start)
    return list(session.execute(stmt).all())


def fetch_document(session: Session, document_id: str) -> sa.Row[Any] | None:
    stmt = sa.select(documents).where(documents.c.id == document_id)
    return session.execute(stmt).first()


def fetch_document_by_short_key(session: Session, short_key: str) -> sa.Row[Any] | None:
    stmt = sa.select(documents).where(documents.c.short_key == short_key)
    return session.execute(stmt).first()


def dense_search(
    session: Session,
    corpus_version_id: str,
    jurisdictions: list[str],
    as_of: date,
    query_vector: list[float],
    top_n: int = 40,
    doc_types: list[str] | None = None,
) -> list[tuple[sa.Row[Any], float]]:
    """Cosine-similarity search over `chunks.embedding` (BGE-M3, HNSW index, §6.5).

    Returns `(row, similarity)` pairs, `similarity` in [-1, 1] (1 = identical), ranked
    descending. `cosine_distance` is `1 - cosine_similarity`, so we sort by it ascending and
    report the similarity back to the caller for confidence scoring (§6.7).
    """
    base = retrievable_chunks(corpus_version_id, jurisdictions, as_of, doc_types)
    distance = chunks.c.embedding.cosine_distance(query_vector)
    stmt = base.add_columns(distance.label("distance")).order_by(distance).limit(top_n)
    rows = session.execute(stmt).all()
    return [(row, 1.0 - row.distance) for row in rows]


def keyword_search(
    session: Session,
    corpus_version_id: str,
    jurisdictions: list[str],
    as_of: date,
    tsquery: str,
    top_n: int = 40,
    doc_types: list[str] | None = None,
) -> list[tuple[sa.Row[Any], float]]:
    """Full-text search over `chunks.tsv` via `websearch_to_tsquery('english', …)` (§6.5).

    `tsquery` is the raw user/query text; Postgres does the query-string parsing. Returns
    `(row, ts_rank)` pairs ranked descending.
    """
    base = retrievable_chunks(corpus_version_id, jurisdictions, as_of, doc_types)
    query = sa.func.websearch_to_tsquery("english", tsquery)
    rank = sa.func.ts_rank(chunks.c.tsv, query)
    stmt = (
        base.add_columns(rank.label("rank"))
        .where(chunks.c.tsv.op("@@")(query))
        .order_by(rank.desc())
        .limit(top_n)
    )
    rows = session.execute(stmt).all()
    return [(row, float(row.rank)) for row in rows]


def trigram_search(
    session: Session,
    corpus_version_id: str,
    jurisdictions: list[str],
    as_of: date,
    text: str,
    top_n: int = 10,
) -> list[tuple[sa.Row[Any], float]]:
    """Trigram match on `sections.section_key`/`heading` (§6.5) — finds "3(p)"-style queries
    that `websearch_to_tsquery` tokenises badly. Joins through `sections` but still gates on
    `retrievable_chunks` for the chunk rows it returns.
    """
    similarity = sa.func.greatest(
        sa.func.similarity(sections.c.section_key, text),
        sa.func.similarity(sa.func.coalesce(sections.c.heading, ""), text),
    )
    eligible_sections = (
        retrievable_chunks(corpus_version_id, jurisdictions, as_of)
        .with_only_columns(chunks.c.section_id)
        .distinct()
        .subquery()
    )
    sec_stmt = (
        sa.select(sections.c.id, similarity.label("similarity"))
        .where(
            similarity > 0.2,
            sections.c.id.in_(sa.select(eligible_sections.c.section_id)),
        )
        .order_by(similarity.desc())
        .limit(top_n)
    )
    matched_sections = session.execute(sec_stmt).all()
    if not matched_sections:
        return []
    sim_by_section = {str(r.id): r.similarity for r in matched_sections}
    base = retrievable_chunks(corpus_version_id, jurisdictions, as_of)
    stmt = base.where(chunks.c.section_id.in_(sim_by_section.keys()))
    rows = session.execute(stmt).all()
    return [(row, float(sim_by_section[str(row.section_id)])) for row in rows]


def fetch_chunks_for_sections(
    session: Session,
    section_ids: list[str],
    corpus_version_id: str,
    jurisdictions: list[str],
    as_of: date,
) -> list[sa.Row[Any]]:
    if not section_ids:
        return []
    base = retrievable_chunks(corpus_version_id, jurisdictions, as_of)
    stmt = base.where(chunks.c.section_id.in_(section_ids))
    return list(session.execute(stmt).all())


def all_chunks_ordered(session: Session, corpus_version_id: str) -> list[sa.Row[Any]]:
    """Every chunk in a corpus version, in a fixed deterministic order (by id).

    This is the Merkle tree's leaf order (§6.9) — `ingest/versions.py::promote` and
    `audit/receipts.py::verify` must both call this rather than each rolling their own
    query, or the two could disagree on leaf order and every proof would fail.
    """
    stmt = (
        sa.select(chunks.c.id, chunks.c.sha256)
        .where(chunks.c.corpus_version_id == corpus_version_id)
        .order_by(chunks.c.id)
    )
    return list(session.execute(stmt).all())


def find_chunk_by_evidence_id(
    session: Session, corpus_version_id: str, evidence_id_fn: Any, evidence_id: str
) -> sa.Row[Any] | None:
    """Scans a version's chunks for the one whose `stable_evidence_id` matches. There's no
    reverse index (it's a one-way hash of chunk_id + offsets) — fine at prototype scale; a
    dedicated `evidence_id` column would be the fix at real scale.
    """
    stmt = sa.select(chunks).where(chunks.c.corpus_version_id == corpus_version_id)
    for row in session.execute(stmt).all():
        if evidence_id_fn(str(row.id), row.char_start, row.char_end) == evidence_id:
            return row
    return None


def chunk_current_text_and_id(session: Session, chunk_id: str) -> sa.Row[Any] | None:
    stmt = sa.select(chunks.c.id, chunks.c.text, chunks.c.section_id).where(chunks.c.id == chunk_id)
    return session.execute(stmt).first()


def graph_expand(
    session: Session,
    section_ids: list[str],
    corpus_version_id: str,
    kinds: tuple[str, ...] = ("defined_in", "proviso_of", "exception_to", "amends"),
    depth: int = 1,
) -> list[str]:
    """1-hop (by default) expansion over `edges`, returning newly-reached section IDs.

    Depth is a plain Python loop rather than a recursive CTE: `depth` is always small (≤1 in
    practice per §6.5) and a loop keeps the jurisdiction/as-of re-filtering explicit at the
    chunk-fetch call site instead of buried inside a CTE.
    """
    frontier = set(section_ids)
    reached: set[str] = set()
    for _ in range(max(depth, 0)):
        if not frontier:
            break
        stmt = sa.select(edges.c.dst_section_id).where(
            edges.c.src_section_id.in_(frontier),
            edges.c.corpus_version_id == corpus_version_id,
            edges.c.kind.in_(kinds),
        )
        next_frontier = {str(r.dst_section_id) for r in session.execute(stmt).all()}
        next_frontier -= reached
        reached |= next_frontier
        frontier = next_frontier
    return list(reached)
