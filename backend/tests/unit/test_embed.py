import httpx
import pytest

from app.config import Settings
from app.retrieval import embed


def test_embeddings_use_local_ollama_bounded_batches_and_normalize(monkeypatch):
    calls = []
    monkeypatch.setattr(embed, "get_settings", lambda: Settings(OLLAMA_NUM_THREADS=2))

    def post(url, **kwargs):
        calls.append((url, kwargs["json"]))
        return httpx.Response(
            200,
            json={"embeddings": [[2.0] + [0.0] * 1023 for _ in kwargs["json"]["input"]]},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(embed.httpx, "post", post)
    vectors = embed.embed_texts(["evidence"] * 9)
    assert len(calls) == 3 and len(vectors) == 9
    assert all(len(call[1]["input"]) <= 4 for call in calls)
    assert calls[0][1]["model"] == "qwen3-embedding:0.6b"
    assert calls[0][1]["options"]["num_thread"] == 2
    assert vectors[0][0] == 1


def test_invalid_vectors_are_rejected(monkeypatch):
    monkeypatch.setattr(
        embed.httpx,
        "post",
        lambda url, **k: httpx.Response(200, json={"embeddings": [[1, 2]]}, request=httpx.Request("POST", url)),
    )
    with pytest.raises(embed.EmbeddingUnavailable):
        embed.embed_query("question")
