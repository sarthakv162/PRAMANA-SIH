import httpx
import pytest
from pydantic import ValidationError

from app.config import Settings
from app.generation import llm
from app.generation.claim_schema import GenerationResult


def response(content: str) -> httpx.Response:
    return httpx.Response(
        200, json={"message": {"content": content}}, request=httpx.Request("POST", "http://localhost/api/chat")
    )


def test_ollama_sends_schema_and_bounded_deterministic_options(monkeypatch):
    monkeypatch.setattr(llm, "get_settings", lambda: Settings(OLLAMA_BASE_URL="http://127.0.0.1:11434", OLLAMA_NUM_THREADS=2))
    calls = []

    def post(url, **kwargs):
        calls.append((url, kwargs))
        return response(
            '{"claims":[{"statement":"Supported statement","evidence_ids":["E1"],"kind":"statement"}],'
            '"gaps":[],"needs_clarification":null}'
        )

    monkeypatch.setattr(llm.httpx, "post", post)
    result = llm.get_llm_client().generate_json(GenerationResult, "Grounded answer", "Evidence E1")
    assert result.claims[0].evidence_ids == ["E1"]
    url, call = calls[0]
    assert url.endswith("/api/chat") and "127.0.0.1" in url
    assert call["json"]["format"] == GenerationResult.model_json_schema()
    assert call["json"]["model"] == "qwen3:4b"
    assert call["json"]["options"]["num_ctx"] <= 8192
    assert call["json"]["options"]["temperature"] == 0
    assert call["json"]["options"]["num_thread"] == 2
    assert call["json"]["think"] is False
    assert "Authorization" not in call.get("headers", {})


def test_invalid_schema_retries_once_then_fails_without_echoing_input(monkeypatch):
    calls = []
    monkeypatch.setattr(llm.httpx, "post", lambda *a, **k: calls.append(k) or response("not json"))
    with pytest.raises(llm.LlmError, match="schema validation") as err:
        llm.get_llm_client().generate_json(GenerationResult, "system", "private user text")
    assert len(calls) == 2 and "private user text" not in str(err.value)


def test_network_failure_does_not_use_other_provider(monkeypatch):
    def fail(*args, **kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(llm.httpx, "post", fail)
    with pytest.raises(llm.LlmError, match="Local Ollama"):
        llm.get_llm_client().generate_text("system", "question")


@pytest.mark.parametrize(
    "settings",
    [
        {"ollama_base_url": "https://api.example.com"},
        {"llm_model": "gemma3:4b"},
        {"embed_model": "BAAI/bge-m3"},
        {"ollama_context_tokens": 16384},
        {"ollama_base_url": "http://ollama.example.com:11434"},
        {"ollama_base_url": "http://ollama:8000"},
        {"ollama_base_url": "http://ollama:11434/remote"},
        {"ollama_base_url": "http://user:secret@ollama:11434"},
    ],
)
def test_rejects_remote_or_unbudgeted_models(settings):
    with pytest.raises(ValidationError):
        Settings(**settings)


def test_accepts_same_server_ollama_service_without_enabling_remote_providers():
    settings = Settings(ollama_base_url="http://ollama:11434/")
    assert settings.ollama_base_url == "http://ollama:11434"
    assert settings.llm_model == "qwen3:4b"
    assert settings.embed_model == "qwen3-embedding:0.6b"
