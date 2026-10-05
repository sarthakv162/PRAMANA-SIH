"""Reciprocal Rank Fusion + the hybrid retrieve step (§6.5).

`k=60` is RRF's standard smoothing constant (Cormack et al. 2009), not tuned per corpus.
When `jurisdictions` has more than one entry, fusion runs **per jurisdiction bucket** first so
INTL results can never outrank IN ones purely by volume — each bucket is fused independently
and then interleaved, so a `BOTH` query always retrieves top-N *per jurisdiction*, matching §6.5.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy.orm import Session

from app.config import get_settings
from app.retrieval import embed, keyword, repo

RRF_K = 60


@dataclass
class Candidate:
    chunk_id: str
    jurisdiction: str
    scores: dict[str, float] = field(default_factory=dict)
    rrf_score: float = 0.0


def _rrf_fuse(ranked_lists: list[list[str]], k: int = RRF_K) -> dict[str, float]:
    fused: dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, chunk_id in enumerate(ranked, start=1):
            fused[chunk_id] = fused.get(chunk_id, 0.0) + 1.0 / (k + rank)
    return fused


def hybrid_retrieve(
    session: Session,
    corpus_version_id: str,
    jurisdictions: list[str],
    as_of: date,
    query_en: str,
    top_n_per_jurisdiction: int = 8,
    doc_types: list[str] | None = None,
    doc_keys: list[str] | None = None,
) -> list[Candidate]:
    """Dense + keyword search, RRF-fused, bucketed per jurisdiction, returned interleaved
    (IN before INTL — §5.2's ordering rule for `AnswerCard.sections`).
    """
    query_vector = None
    if repo.embedding_model_for_version(session, corpus_version_id) == get_settings().embed_model:
        try:
            query_vector = embed.embed_query(query_en)
        except embed.EmbeddingUnavailable:
            pass  # Keyword retrieval still uses the same authoritative, pinned corpus.

    all_candidates: dict[str, Candidate] = {}
    ordered_ids_by_jurisdiction: dict[str, list[str]] = {}

    for jurisdiction in jurisdictions:
        dense = (
            repo.dense_search(
                session,
                corpus_version_id,
                [jurisdiction],
                as_of,
                query_vector,
                top_n=40,
                doc_types=doc_types,
                doc_keys=doc_keys,
            )
            if query_vector is not None
            else []
        )
        # Dense-only matches must clear a relevance floor; distant neighbors are not evidence.
        dense = [(row, score) for row, score in dense if score >= 0.45]
        kw = keyword.keyword_search(
            session,
            corpus_version_id,
            [jurisdiction],
            as_of,
            query_en,
            top_n=40,
            doc_types=doc_types,
            doc_keys=doc_keys,
        )

        dense_ranked = [str(row.id) for row, _ in dense]
        kw_ranked = [chunk_id for chunk_id, _ in kw]
        fused = _rrf_fuse([dense_ranked, kw_ranked])

        dense_scores = {str(row.id): score for row, score in dense}
        kw_scores = dict(kw)

        for chunk_id in fused:
            candidate = all_candidates.setdefault(chunk_id, Candidate(chunk_id=chunk_id, jurisdiction=jurisdiction))
            candidate.scores["dense"] = dense_scores.get(chunk_id, 0.0)
            candidate.scores["fts"] = kw_scores.get(chunk_id, 0.0)
            candidate.scores["rrf"] = fused[chunk_id]
            candidate.rrf_score = fused[chunk_id]

        top_ids = sorted(fused, key=lambda cid: fused[cid], reverse=True)[:top_n_per_jurisdiction]
        ordered_ids_by_jurisdiction[jurisdiction] = top_ids

    ordered: list[Candidate] = []
    for jurisdiction in jurisdictions:
        for chunk_id in ordered_ids_by_jurisdiction.get(jurisdiction, []):
            ordered.append(all_candidates[chunk_id])
    return ordered


def top1_top2_margin(candidates: list[Candidate]) -> float:
    """Score-margin between the best and second-best fused result (§6.5 `RERANK_SKIP_MARGIN`,
    §6.7 `confidence.retrieval_margin`). 1.0 (max confidence) if fewer than 2 candidates.
    """
    if len(candidates) < 2:
        return 1.0
    ranked = sorted(candidates, key=lambda c: c.rrf_score, reverse=True)
    top1, top2 = ranked[0].rrf_score, ranked[1].rrf_score
    if top1 <= 0:
        return 0.0
    return (top1 - top2) / top1
