"""Keyword-side retrieval (§6.5): full-text search plus a trigram fallback for citation-shaped
queries like "3(p)" that `websearch_to_tsquery` tokenises badly (it drops bare punctuation).

Both signals go through `retrieval/repo.py` — this module never touches `chunks` directly.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.retrieval import repo


def keyword_search(
    session: Session,
    corpus_version_id: str,
    jurisdictions: list[str],
    as_of: date,
    query_en: str,
    top_n: int = 40,
    doc_types: list[str] | None = None,
) -> list[tuple[str, float]]:
    """Return `(chunk_id, score)` pairs, FTS and trigram results merged (FTS first, since it's
    the stronger general-purpose signal; trigram only adds hits FTS missed).
    """
    fts = repo.keyword_search(
        session, corpus_version_id, jurisdictions, as_of, query_en, top_n, doc_types
    )
    results: dict[str, float] = {str(row.id): score for row, score in fts}

    trigram = repo.trigram_search(
        session, corpus_version_id, jurisdictions, as_of, query_en, top_n=10
    )
    for row, score in trigram:
        chunk_id = str(row.id)
        if chunk_id not in results:
            results[chunk_id] = score

    return sorted(results.items(), key=lambda kv: kv[1], reverse=True)
