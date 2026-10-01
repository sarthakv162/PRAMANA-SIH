from __future__ import annotations

import json

import httpx
import pytest

from app.generation.claim_schema import GenerationResult
from app.generation.llm import GroqClient, LlmError


def _completion(content: str, *, status: int = 200) -> httpx.Response:
    return httpx.Response(
        status,
        json={"choices": [{"message": {"content": content}}]},
        request=httpx.Request("POST", GroqClient._endpoint),
    )


def test_groq_json_uses_strict_schema_and_validates_response(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []

    def fake_post(url: str, **kwargs: object) -> httpx.Response:
        assert url == GroqClient._endpoint
        calls.append(kwargs)
        return _completion('{"claims": [], "gaps": [], "needs_clarification": null}')

    monkeypatch.setattr(httpx, "post", fake_post)
    result = GroqClient(model="openai/gpt-oss-120b", api_key="test-key").generate_json(
        GenerationResult, system="system", user="user"
    )

    assert result == GenerationResult(claims=[], gaps=[], needs_clarification=None)
    body = calls[0]["json"]
    assert isinstance(body, dict)
    assert body["model"] == "openai/gpt-oss-120b"
    assert body["temperature"] == 0
    response_format = body["response_format"]
    assert isinstance(response_format, dict)
    strict_schema = response_format["json_schema"]
    assert isinstance(strict_schema, dict)
    assert strict_schema["strict"] is True
    schema = strict_schema["schema"]
    assert isinstance(schema, dict)
    assert set(schema["required"]) == {"claims", "gaps", "needs_clarification"}
    assert schema["additionalProperties"] is False
    definitions = schema["$defs"]
    assert isinstance(definitions, dict)
    raw_claim = definitions["RawClaim"]
    assert isinstance(raw_claim, dict)
    assert set(raw_claim["required"]) == {"statement", "evidence_ids", "kind"}
    assert raw_claim["additionalProperties"] is False


def test_groq_json_retries_once_after_pydantic_validation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    outputs = iter(
        [
            json.dumps(
                {
                    "claims": [{"statement": "claim", "evidence_ids": [], "kind": "statement"}],
                    "gaps": [],
                    "needs_clarification": None,
                }
            ),
            json.dumps({"claims": [], "gaps": [], "needs_clarification": None}),
        ]
    )
    calls = 0

    def fake_post(_url: str, **_kwargs: object) -> httpx.Response:
        nonlocal calls
        calls += 1
        return _completion(next(outputs))

    monkeypatch.setattr(httpx, "post", fake_post)
    result = GroqClient(model="openai/gpt-oss-120b", api_key="test-key").generate_json(
        GenerationResult, system="system", user="user"
    )

    assert result.claims == []
    assert calls == 2


def test_groq_text_and_provider_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(httpx, "post", lambda *_args, **_kwargs: _completion("translated text"))
    client = GroqClient(model="openai/gpt-oss-120b", api_key="test-key")
    assert client.generate_text("system", "user") == "translated text"

    monkeypatch.setattr(httpx, "post", lambda *_args, **_kwargs: _completion("unauthorized", status=401))
    with pytest.raises(LlmError, match="HTTP 401") as caught:
        client.generate_text("system", "user")
    assert "test-key" not in str(caught.value)


def test_groq_requires_an_api_key() -> None:
    with pytest.raises(LlmError, match="GROQ_API_KEY"):
        GroqClient(model="openai/gpt-oss-120b", api_key="")
