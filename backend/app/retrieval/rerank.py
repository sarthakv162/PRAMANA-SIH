"""Reranking remains disabled in the 16 GB local deployment.

Preserve the retrieval interface without importing another transformer model. The
configured Qwen embedding model and reciprocal-rank fusion supply candidate ordering.
"""

from __future__ import annotations

from app.retrieval.rrf import Candidate


def maybe_rerank(
    query_en: str,
    candidates: list[Candidate],
    texts_by_chunk_id: dict[str, str],
    top_n: int = 8,
) -> list[Candidate]:
    return candidates[:top_n]
