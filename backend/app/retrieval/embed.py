"""Qwen3 multilingual embeddings through native, local Ollama (1024 dimensions)."""

from __future__ import annotations

import math

import httpx

from app.config import get_settings
from app.generation.llm import INFERENCE_LOCK

EMBED_BATCH_SIZE = 4
EMBED_DIMENSIONS = 1024


class EmbeddingUnavailable(Exception):
    pass


def embed_texts(texts: list[str]) -> list[list[float]]:
    settings = get_settings()
    if settings.inference_runtime == "transformers":
        from app.generation.transformers_runtime import embed_texts as transformer_embeddings

        return transformer_embeddings(texts)
    options = {"num_ctx": 2048}
    if settings.ollama_num_threads is not None:
        options["num_thread"] = settings.ollama_num_threads
    vectors: list[list[float]] = []
    for offset in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[offset : offset + EMBED_BATCH_SIZE]
        try:
            with INFERENCE_LOCK:
                response = httpx.post(
                    f"{settings.ollama_base_url}/api/embed",
                    json={
                        "model": settings.embed_model,
                        "input": batch,
                        "dimensions": EMBED_DIMENSIONS,
                        "keep_alive": settings.ollama_keep_alive,
                        "options": options,
                    },
                    timeout=settings.request_deadline_s,
                )
            response.raise_for_status()
            output = response.json()["embeddings"]
            if not isinstance(output, list) or len(output) != len(batch):
                raise ValueError("embedding batch count mismatch")
            for vector in output:
                if len(vector) != EMBED_DIMENSIONS or not all(math.isfinite(v) for v in vector):
                    raise ValueError("invalid embedding dimensions/values")
                norm = math.sqrt(sum(v * v for v in vector))
                if norm == 0:
                    raise ValueError("zero embedding")
                vectors.append([v / norm for v in vector])
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise EmbeddingUnavailable(
                "Local embeddings unavailable. Start Ollama and pull qwen3-embedding:0.6b."
            ) from exc
    return vectors


def embed_query(text: str) -> list[float]:
    return embed_texts([f"Instruct: Retrieve authoritative legal evidence for the question.\nQuery: {text}"])[0]
