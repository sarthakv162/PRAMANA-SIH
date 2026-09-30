"""Optional cross-encoder reranking (`RERANK=1`, §6.5). Cut-line item #4 (§10) — off by
default. When enabled, reranks the top 20 fused candidates down to 8 with
`bge-reranker-v2-m3`, skipping the model call entirely when the RRF top-1/top-2 margin
already exceeds `RERANK_SKIP_MARGIN` (a wide margin means the fusion result is already
confident, so paying for a rerank pass buys nothing).
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from app.config import get_settings
from app.retrieval.rrf import Candidate, top1_top2_margin

if TYPE_CHECKING:
    from sentence_transformers import CrossEncoder


@lru_cache
def _model() -> CrossEncoder:
    from sentence_transformers import CrossEncoder

    return CrossEncoder("BAAI/bge-reranker-v2-m3", device="cpu")  # type: ignore[no-any-return]


def maybe_rerank(
    query_en: str,
    candidates: list[Candidate],
    texts_by_chunk_id: dict[str, str],
    top_n: int = 8,
) -> list[Candidate]:
    settings = get_settings()
    if not settings.rerank:
        return candidates[:top_n]
    if top1_top2_margin(candidates) > settings.rerank_skip_margin:
        return candidates[:top_n]

    model = _model()
    pairs = [
        (query_en, texts_by_chunk_id[c.chunk_id])
        for c in candidates
        if c.chunk_id in texts_by_chunk_id
    ]
    if not pairs:
        return candidates[:top_n]
    scores = model.predict(pairs)
    for candidate, score in zip(candidates, scores, strict=False):
        candidate.scores["rerank"] = float(score)
    reranked = sorted(candidates, key=lambda c: c.scores.get("rerank", c.rrf_score), reverse=True)
    return reranked[:top_n]
