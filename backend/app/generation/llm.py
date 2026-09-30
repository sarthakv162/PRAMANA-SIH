"""LLM adapter (§6.6, §6.13 `LLM_PROVIDER`/`LLM_MODEL`). One method, `generate_json`, used by
every caller that needs model output: schema-constrained (Anthropic tool-use forces the
shape), Pydantic-validated, one retry on invalid output. (§6.6 also asks for temperature 0;
the installed SDK's `messages.create` no longer exposes a `temperature` parameter at all, so
determinism here rests on tool-forced JSON output instead.)

Only `anthropic` is implemented. The other providers named in §6.13 are real switch cases
that raise a clear `NotImplementedError` rather than silently falling back to a different
model — swapping providers is a deployment decision for whoever runs this with their own
key, not something to guess at.
"""

from __future__ import annotations

from typing import TypeVar

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

        self._client = anthropic.Anthropic(api_key=api_key)
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


_PROVIDERS = {"anthropic": AnthropicClient}


def get_llm_client() -> LlmClient:
    settings = get_settings()
    provider_cls = _PROVIDERS.get(settings.llm_provider)
    if provider_cls is None:
        raise NotImplementedError(
            f"LLM_PROVIDER={settings.llm_provider!r} is not implemented; only 'anthropic' is."
        )
    return provider_cls(model=settings.llm_model, api_key=settings.llm_api_key)
