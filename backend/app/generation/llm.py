"""LLM adapters for Groq and Anthropic.

Groq is the configured default. JSON generation uses strict structured output followed by
Pydantic validation and one retry if the returned payload is invalid. Anthropic remains
available for existing deployments using its tool-use schema contract.
"""

from __future__ import annotations

import json
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.config import get_settings

T = TypeVar("T", bound=BaseModel)


class LlmError(Exception):
    pass


class LlmClient:
    """Thin wrapper so callers depend on this interface, not the Anthropic SDK directly —
    swappable in tests via a fake with the same two methods.
    """

    def generate_json(self, schema: type[T], system: str, user: str) -> T:
        raise NotImplementedError

    def generate_text(self, system: str, user: str) -> str:
        raise NotImplementedError


class AnthropicClient(LlmClient):
    def __init__(self, model: str, api_key: str) -> None:
        if not api_key:
            raise LlmError(
                "LLM_API_KEY is not set — required to call the Anthropic API. "
                "Set it in .env (see .env.example)."
            )
        import anthropic

        # Keep a stalled provider call within the API's configured request budget. SDK retries
        # are disabled because generate_json already owns the single schema-validation retry.
        from app.config import get_settings

        self._client = anthropic.Anthropic(
            api_key=api_key,
            timeout=get_settings().request_deadline_s,
            max_retries=0,
        )
        self._model = model

    def generate_text(self, system: str, user: str) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=2048,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(block.text for block in response.content if block.type == "text")

    def generate_json(self, schema: type[T], system: str, user: str) -> T:
        tool_name = "emit_result"
        tool = {
            "name": tool_name,
            "description": "Emit the result in the required schema.",
            "input_schema": schema.model_json_schema(),
        }
        last_error: Exception | None = None
        for _attempt in range(2):  # one retry on invalid output (§6.6)
            # Plain dicts here match the Anthropic API's actual JSON shape for tool-use;
            # mypy wants the SDK's TypedDict variants specifically, which isn't worth the
            # verbosity for a prototype adapter.
            response = self._client.messages.create(  # type: ignore[call-overload]
                model=self._model,
                max_tokens=2048,
                system=system,
                messages=[{"role": "user", "content": user}],
                tools=[tool],
                tool_choice={"type": "tool", "name": tool_name},
            )
            tool_use = next(
                (b for b in response.content if b.type == "tool_use" and b.name == tool_name),
                None,
            )
            if tool_use is None:
                last_error = LlmError("model did not call the required tool")
                continue
            try:
                return schema.model_validate(tool_use.input)
            except ValidationError as exc:
                last_error = exc
                user = (
                    f"{user}\n\nYour previous output was invalid: {exc}\n"
                    f"Emit valid JSON matching the schema exactly."
                )
        raise LlmError(f"model output failed validation twice: {last_error}")


class GroqClient(LlmClient):
    """Small HTTPX adapter for Groq's OpenAI-compatible Chat Completions API."""

    _endpoint = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self, model: str, api_key: str) -> None:
        if not api_key:
            raise LlmError(
                "GROQ_API_KEY is not set — required to call Groq. Set it in .env (see .env.example)."
            )
        self._model = model
        self._api_key = api_key

    def _complete(
        self, system: str, user: str, *, response_format: dict[str, object] | None = None
    ) -> str:
        from app.config import get_settings

        body: dict[str, object] = {
            "model": self._model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "max_completion_tokens": 2048,
            "temperature": 0,
        }
        if response_format is not None:
            body["response_format"] = response_format

        try:
            response = httpx.post(
                self._endpoint,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json=body,
                timeout=get_settings().request_deadline_s,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            # Do not echo provider response bodies: they can contain submitted user text.
            raise LlmError(f"Groq API returned HTTP {exc.response.status_code}.") from exc
        except httpx.RequestError as exc:
            raise LlmError(f"Groq request failed ({type(exc).__name__}).") from exc

        try:
            choices = response.json()["choices"]
            content = choices[0]["message"]["content"]
        except (IndexError, KeyError, TypeError, ValueError) as exc:
            raise LlmError("Groq returned an invalid chat completion response.") from exc
        if not isinstance(content, str) or not content.strip():
            raise LlmError("Groq returned an empty chat completion.")
        return content

    def generate_text(self, system: str, user: str) -> str:
        return self._complete(system, user)

    def generate_json(self, schema: type[T], system: str, user: str) -> T:
        json_schema = schema.model_json_schema()
        _make_strict_json_schema(json_schema)
        response_format: dict[str, object] = {
            "type": "json_schema",
            "json_schema": {
                "name": schema.__name__.lower(),
                "strict": True,
                "schema": json_schema,
            },
        }

        last_error: Exception | None = None
        for _attempt in range(2):
            try:
                content = self._complete(system, user, response_format=response_format)
                return schema.model_validate(json.loads(content))
            except (json.JSONDecodeError, ValidationError) as exc:
                last_error = exc
                user = (
                    f"{user}\n\nYour previous output failed schema validation. "
                    "Return valid JSON matching the required schema exactly."
                )
        raise LlmError(f"model output failed validation twice: {last_error}")


def _make_strict_json_schema(node: object) -> None:
    """Apply the required-field and no-extra-properties rules for Groq strict mode."""
    if isinstance(node, dict):
        properties = node.get("properties")
        if isinstance(properties, dict):
            node["required"] = list(properties)
            node["additionalProperties"] = False
            for child in properties.values():
                _make_strict_json_schema(child)
        for key, value in node.items():
            if key != "properties":
                _make_strict_json_schema(value)
    elif isinstance(node, list):
        for child in node:
            _make_strict_json_schema(child)


_PROVIDERS = {"anthropic": AnthropicClient, "groq": GroqClient}


def get_llm_client() -> LlmClient:
    settings = get_settings()
    provider_cls = _PROVIDERS.get(settings.llm_provider)
    if provider_cls is None:
        raise NotImplementedError(
            f"LLM_PROVIDER={settings.llm_provider!r} is not implemented; use 'groq' or 'anthropic'."
        )
    api_key = (
        settings.groq_api_key or settings.llm_api_key
        if settings.llm_provider == "groq"
        else settings.llm_api_key
    )
    return provider_cls(model=settings.llm_model, api_key=api_key)
