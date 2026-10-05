"""Local Ollama inference. There are no cloud providers or model fallbacks."""

from __future__ import annotations

import json
import threading
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.config import get_settings

T = TypeVar("T", bound=BaseModel)
# One inference at a time bounds KV-cache/verification memory on the 16 GB target.
INFERENCE_LOCK = threading.RLock()


class LlmError(Exception):
    pass


class LlmClient:
    def generate_json(self, schema: type[T], system: str, user: str) -> T:
        raise NotImplementedError

    def generate_text(self, system: str, user: str) -> str:
        raise NotImplementedError


class OllamaClient(LlmClient):
    def _complete(self, system: str, user: str, schema: dict[str, object] | None = None) -> str:
        settings = get_settings()
        options: dict[str, int | float] = {
            "num_ctx": settings.ollama_context_tokens, "temperature": 0, "num_predict": 1536,
        }
        if settings.ollama_num_threads is not None:
            options["num_thread"] = settings.ollama_num_threads
        body: dict[str, object] = {
            "model": settings.llm_model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "stream": False,
            "think": False,
            "keep_alive": settings.ollama_keep_alive,
            "options": options,
        }
        if schema is not None:
            body["format"] = schema
        try:
            with INFERENCE_LOCK:
                response = httpx.post(
                    f"{settings.ollama_base_url}/api/chat",
                    json=body,
                    timeout=settings.request_deadline_s,
                )
            response.raise_for_status()
            payload = response.json()
            content = payload["message"]["content"]
            if payload.get("done_reason") == "length":
                raise LlmError("Local generation exceeded its output limit; no verified synthesis is available.")
            if not isinstance(content, str) or not content.strip():
                raise ValueError("empty response")
            return content
        except httpx.HTTPStatusError as exc:
            raise LlmError(
                f"Local Ollama returned HTTP {exc.response.status_code}. Check the requested model is pulled."
            ) from exc
        except (httpx.RequestError, ValueError, KeyError, TypeError) as exc:
            raise LlmError("Local Ollama generation is unavailable. Start Ollama and pull qwen3:4b.") from exc

    def generate_json(self, schema: type[T], system: str, user: str) -> T:
        json_schema = schema.model_json_schema()
        for attempt in range(2):
            content = self._complete(system, user, json_schema)
            try:
                return schema.model_validate_json(content)
            except (ValidationError, json.JSONDecodeError):
                if attempt == 1:
                    raise LlmError(
                        "Local model output failed schema validation; no verified synthesis is available."
                    ) from None
                user += "\nReturn only valid JSON matching the required schema exactly."
        raise LlmError("No schema-valid output received.")

    def generate_text(self, system: str, user: str) -> str:
        return self._complete(system, user)


def get_llm_client() -> LlmClient:
    return OllamaClient()
