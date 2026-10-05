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

import re
from datetime import date
from typing import Any

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Session

from app.core.sql_types import UUID

metadata = sa.MetaData()

corpus_versions = sa.Table(
    "corpus_versions",
    metadata,
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("label", sa.Text),
    sa.Column("status", sa.Text),
    sa.Column("merkle_root", sa.Text),
    sa.Column("created_at", sa.DateTime(timezone=True)),
    sa.Column("notes", sa.Text),
    sa.Column("embedding_model", sa.Text),
)

documents = sa.Table(
    "documents",
    metadata,
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
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
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("document_id", UUID(as_uuid=True)),
    sa.Column("corpus_version_id", UUID(as_uuid=True)),
    sa.Column("section_key", sa.Text),
    sa.Column("path", sa.ARRAY(sa.Text).with_variant(sa.JSON(), "sqlite")),
    sa.Column("heading", sa.Text),
    sa.Column("parent_id", UUID(as_uuid=True)),
    sa.Column("effective_from", sa.Date),
    sa.Column("effective_to", sa.Date),
    sa.Column("supersedes_id", UUID(as_uuid=True)),
    sa.Column("page_start", sa.Integer),
    sa.Column("page_end", sa.Integer),
    sa.Column("text", sa.Text),
    sa.Column("sha256", sa.Text),
)

chunks = sa.Table(
    "chunks",
    metadata,
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("section_id", UUID(as_uuid=True)),
    sa.Column("corpus_version_id", UUID(as_uuid=True)),
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
    sa.Column("bboxes", sa.dialects.postgresql.JSONB().with_variant(sa.JSON(), "sqlite")),
    sa.Column("embedding", Vector(1024).with_variant(sa.JSON(), "sqlite")),
    sa.Column("tsv", TSVECTOR().with_variant(sa.Text(), "sqlite")),
)

edges = sa.Table(
    "edges",
    metadata,
    sa.Column("src_section_id", UUID(as_uuid=True)),
    sa.Column("dst_section_id", UUID(as_uuid=True)),
    sa.Column("kind", sa.Text),
    sa.Column("corpus_version_id", UUID(as_uuid=True)),
)


def retrievable_chunks(
    corpus_version_id: str,
    jurisdictions: list[str],
    as_of: date,
    doc_types: list[str] | None = None,
    doc_keys: list[str] | None = None,
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
    if doc_keys is not None:
        stmt = stmt.where(
            chunks.c.section_id.in_(
                sa.select(sections.c.id)
                .join(documents, sections.c.document_id == documents.c.id)
                .where(documents.c.short_key.in_(doc_keys))
            )
        )
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
    row = session.execute(sa.select(corpus_versions.c.id).where(corpus_versions.c.label == label)).first()
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


def ancestor_section_ids(
    session: Session, section_ids: list[str], corpus_version_id: str, max_depth: int = 4
) -> list[str]:
    """Return parent IDs for retrieved clause/subsection rows.

    Clause text can omit its parent's introductory language (for example, a clause defines
    what kind of "invention" it is while the section heading says those things "are not
    inventions"). Retrieval needs that heading as context for generation and verification.
    """
    visited = set(section_ids)
    frontier = set(section_ids)
    ancestors: set[str] = set()
    for _ in range(max_depth):
        if not frontier:
            break
        stmt = sa.select(sections.c.id, sections.c.parent_id).where(
            sections.c.id.in_(frontier),
            sections.c.corpus_version_id == corpus_version_id,
        )
        next_frontier = {
            str(row.parent_id)
            for row in session.execute(stmt).all()
            if row.parent_id is not None and str(row.parent_id) not in visited
        }
        visited.update(next_frontier)
        ancestors.update(next_frontier)
        frontier = next_frontier
    return sorted(ancestors)


def fetch_section_by_key(session: Session, section_key: str, corpus_version_id: str) -> sa.Row[Any] | None:
    stmt = sa.select(sections).where(
        sections.c.section_key == section_key,
        sections.c.corpus_version_id == corpus_version_id,
    )
    row = session.execute(stmt).first()
    if row is not None or "#s" not in section_key:
        return row
    # Older rule parsers used section-style keys; newer rule headings use #r. Resolve
    # only an actual rule document and retain the database's canonical citation key.
    doc_key, suffix = section_key.split("#s", 1)
    alternate = (
        sa.select(sections)
        .join(documents, sections.c.document_id == documents.c.id)
        .where(
            sections.c.section_key == f"{doc_key}#r{suffix}",
            sections.c.corpus_version_id == corpus_version_id,
            documents.c.short_key == doc_key,
            documents.c.doc_type == "rule",
        )
    )
    return session.execute(alternate).first()


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
    doc_keys: list[str] | None = None,
) -> list[tuple[sa.Row[Any], float]]:
    """Cosine-similarity search over compatible versioned Qwen embeddings (HNSW index).

    Returns `(row, similarity)` pairs, `similarity` in [-1, 1] (1 = identical), ranked
    descending. `cosine_distance` is `1 - cosine_similarity`, so we sort by it ascending and
    report the similarity back to the caller for confidence scoring (§6.7).
    """
    base = retrievable_chunks(corpus_version_id, jurisdictions, as_of, doc_types, doc_keys)
    if session.get_bind().dialect.name == "sqlite":
        import math

        norm = math.sqrt(sum(v * v for v in query_vector))
        if not norm:
            return []
        scored = []
        for row in session.execute(base).all():
            vector = row.embedding
            if not vector or len(vector) != len(query_vector):
                continue
            denom = norm * math.sqrt(sum(v * v for v in vector))
            if denom:
                scored.append((row, sum(a * b for a, b in zip(vector, query_vector, strict=True)) / denom))
        return sorted(scored, key=lambda item: item[1], reverse=True)[:top_n]
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
    doc_keys: list[str] | None = None,
) -> list[tuple[sa.Row[Any], float]]:
    """Full-text search over `chunks.tsv` via `websearch_to_tsquery('english', …)` (§6.5).

    `tsquery` is the raw user/query text; Postgres does the query-string parsing. Returns
    `(row, ts_rank)` pairs ranked descending.
    """
    base = retrievable_chunks(corpus_version_id, jurisdictions, as_of, doc_types, doc_keys)
    words = re.findall(r"\w+", tsquery)
    if not words:
        return []
    if session.get_bind().dialect.name == "sqlite":
        # The packaged corpus has a real FTS5 index with Porter stemming and BM25.
        # Reapply the same legal filters before ranking eligible chunks.
        matches = session.execute(
            sa.text("SELECT chunk_id, bm25(chunks_fts) AS rank FROM chunks_fts WHERE chunks_fts MATCH :query"),
            {"query": " OR ".join(f'"{word}"' for word in words)},
        ).all()
        ranks = {row.chunk_id: -float(row.rank) for row in matches}
        rows = session.execute(base.where(chunks.c.id.in_(ranks))).all()
        return sorted(((row, ranks[str(row.id)]) for row in rows), key=lambda item: item[1], reverse=True)[:top_n]
    exact = sa.func.websearch_to_tsquery("english", tsquery)
    # Natural questions rarely put all their lexemes in a single legal clause. Prefer
    # exact matches, then rank relaxed matches by proximity with document-length
    # normalization. Bound, quoted words keep operators/punctuation out of the query.
    query = sa.func.websearch_to_tsquery("english", " OR ".join(f'"{word}"' for word in words))
    rank = sa.func.ts_rank_cd(chunks.c.tsv, query, 2)
    stmt = (
        base.add_columns(rank.label("rank"))
        .where(chunks.c.tsv.op("@@")(query))
        .order_by(chunks.c.tsv.op("@@")(exact).desc(), rank.desc())
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
    doc_keys: list[str] | None = None,
) -> list[tuple[sa.Row[Any], float]]:
    """Trigram match on `sections.section_key`/`heading` (§6.5) — finds "3(p)"-style queries
    that `websearch_to_tsquery` tokenises badly. Joins through `sections` but still gates on
    `retrievable_chunks` for the chunk rows it returns.
    """
    if session.get_bind().dialect.name == "sqlite":
        from difflib import SequenceMatcher

        eligible = session.execute(retrievable_chunks(corpus_version_id, jurisdictions, as_of, doc_keys=doc_keys)).all()
        by_id = {
            str(row.id): row for row in fetch_sections_by_ids(session, list({str(r.section_id) for r in eligible}))
        }
        scores = {
            key: max(
                SequenceMatcher(None, text.lower(), (value or "").lower()).ratio()
                for value in (row.section_key, row.heading)
            )
            for key, row in by_id.items()
        }
        ranked = [(row, scores[str(row.section_id)]) for row in eligible if scores[str(row.section_id)] > 0.2]
        return sorted(ranked, key=lambda item: item[1], reverse=True)[:top_n]
    similarity = sa.func.greatest(
        sa.func.similarity(sections.c.section_key, text),
        sa.func.similarity(sa.func.coalesce(sections.c.heading, ""), text),
    )
    eligible_sections = (
        retrievable_chunks(corpus_version_id, jurisdictions, as_of, doc_keys=doc_keys)
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
    base = retrievable_chunks(corpus_version_id, jurisdictions, as_of, doc_keys=doc_keys)
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


def all_chunks_ordered(session: Session, corpus_version_id: str) -> list[sa.Row[Any, Any]]:
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


def chunk_current_text_and_id(session: Session, chunk_id: str) -> sa.Row[Any, Any, Any] | None:
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


def embedding_model_for_version(session: Session, version_id: str) -> str | None:
    return session.execute(
        sa.select(corpus_versions.c.embedding_model).where(corpus_versions.c.id == version_id)
    ).scalar_one_or_none()


def documents_for_version(session: Session, version_id: str) -> list[Any]:
    return list(
        session.execute(
            sa.select(documents).where(
                documents.c.id.in_(sa.select(sections.c.document_id).where(sections.c.corpus_version_id == version_id))
            )
        ).all()
    )


document_versions = sa.Table(
    "document_versions",
    metadata,
    sa.Column("document_id", sa.Uuid(as_uuid=False), primary_key=True),
    sa.Column("corpus_version_id", sa.Uuid(as_uuid=False), primary_key=True),
    sa.Column("pdf_path", sa.Text),
    sa.Column("file_sha256", sa.Text),
    sa.Column("source_url", sa.Text),
)


def document_artifact(session: Session, doc_key: str, version_label: str) -> Any:
    return (
        session.execute(
            sa.select(document_versions.c.pdf_path, document_versions.c.file_sha256, document_versions.c.source_url)
            .select_from(
                document_versions.join(documents, document_versions.c.document_id == documents.c.id).join(
                    corpus_versions, document_versions.c.corpus_version_id == corpus_versions.c.id
                )
            )
            .where(documents.c.short_key == doc_key, corpus_versions.c.label == version_label)
        )
        .mappings()
        .first()
    )


def snapshot_rows(session: Session, version_id: str) -> dict[str, list[dict[str, Any]]]:
    """Export one actual live version, without request/history/audit content."""
    section_rows = (
        session.execute(sa.select(sections).where(sections.c.corpus_version_id == version_id)).mappings().all()
    )
    doc_ids = {row["document_id"] for row in section_rows}
    statements = {
        "corpus_versions": sa.select(corpus_versions).where(corpus_versions.c.id == version_id),
        "documents": sa.select(documents).where(documents.c.id.in_(doc_ids)),
        "sections": sa.select(sections).where(sections.c.corpus_version_id == version_id),
        "chunks": sa.select(chunks).where(chunks.c.corpus_version_id == version_id),
        "edges": sa.select(edges).where(edges.c.corpus_version_id == version_id),
        "document_versions": sa.select(document_versions).where(document_versions.c.corpus_version_id == version_id),
    }
    return {name: [dict(row) for row in session.execute(stmt).mappings()] for name, stmt in statements.items()}
