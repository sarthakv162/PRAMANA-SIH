"""Dense embeddings — BGE-M3, 1024-d (§6.5, §6.13 `EMBED_MODEL`).

The model is loaded lazily and cached process-wide: it's a ~2GB checkpoint, so importing this
module must not pay that cost, and nothing should reload it per request. `EMBEDDER=api` is
reserved for a hosted-embedding fallback (§12 "compute limits on hosting") and isn't
implemented yet — the prototype runs the model locally.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from app.config import get_settings

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer


@lru_cache
def _model() -> SentenceTransformer:
    settings = get_settings()
    if settings.embedder != "local":
        raise NotImplementedError(
            f"EMBEDDER={settings.embedder!r} is not implemented; only 'local' is wired up."
        )
    from sentence_transformers import SentenceTransformer

    # CPU-only: this runs alongside other models (NLI, reranker) on modest dev hardware,
    # and an accelerator (MPS/CUDA) queue shared across them has been unreliable here —
    # correctness over speed for a prototype ingest/query path.
    return SentenceTransformer(settings.embed_model, device="cpu")


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Batch-embed `embed_text` strings (heading path + body, §6.2 step 3) for storage."""
    if not texts:
        return []
    model = _model()
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return [v.tolist() for v in vectors]


def embed_query(text: str) -> list[float]:
    """Embed one query string for a similarity search against stored chunk embeddings."""
    return embed_texts([text])[0]
