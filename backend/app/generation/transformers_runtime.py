"""Qwen inference inside a ZeroGPU allocation, with the existing claim schema."""

from __future__ import annotations

from typing import Any, cast

from pydantic import ValidationError

from app.config import answer_model_id, embedding_model_id, get_settings
from app.generation.llm import INFERENCE_LOCK, LlmClient, LlmError, T

ANSWER_REVISION = "1cfa9a7208912126459214e8b04321603b3df60c"
EMBED_REVISION = "97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3"
_answer: Any = None
_answer_tokenizer: Any = None
_embedding: Any = None
_embedding_tokenizer: Any = None


def initialize() -> None:
    """Call at module scope after importing spaces, before starting the server."""
    import torch
    from transformers import AutoModel, AutoModelForCausalLM, AutoTokenizer

    global _answer, _answer_tokenizer, _embedding, _embedding_tokenizer
    _answer_tokenizer = AutoTokenizer.from_pretrained(answer_model_id(), revision=ANSWER_REVISION)
    _answer = (
        cast(Any, AutoModelForCausalLM).from_pretrained(
            answer_model_id(),
            revision=ANSWER_REVISION,
            dtype=torch.float16,
            attn_implementation="sdpa",
        )
        .eval()
        .to("cuda")
    )
    _embedding_tokenizer = AutoTokenizer.from_pretrained(
        embedding_model_id(),
        revision=EMBED_REVISION,
        padding_side="left",
    )
    _embedding = (
        AutoModel.from_pretrained(
            embedding_model_id(),
            revision=EMBED_REVISION,
            dtype=torch.float16,
            attn_implementation="sdpa",
        )
        .eval()
        .to("cuda")
    )


def ready() -> bool:
    return all(item is not None for item in (_answer, _answer_tokenizer, _embedding, _embedding_tokenizer))


class TransformersClient(LlmClient):
    def _complete(self, system: str, user: str, schema: dict[str, Any] | None = None) -> str:
        import torch

        if not ready():
            raise LlmError("ZeroGPU models are unavailable; no verified synthesis is available.")
        settings = get_settings()
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        text = _answer_tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True, enable_thinking=False
        )
        inputs = _answer_tokenizer(text, return_tensors="pt")
        input_length = inputs["input_ids"].shape[-1]
        max_new_tokens = min(1536, settings.ollama_context_tokens - input_length)
        if max_new_tokens < 128:
            raise LlmError("Evidence and follow-up context exceed the 8K generation budget.")
        options: dict[str, Any] = {
            "do_sample": False,
            "max_new_tokens": max_new_tokens,
            "pad_token_id": _answer_tokenizer.eos_token_id,
        }
        if schema is not None:
            from lmformatenforcer import JsonSchemaParser
            from lmformatenforcer.integrations.transformers import build_transformers_prefix_allowed_tokens_fn

            options["prefix_allowed_tokens_fn"] = build_transformers_prefix_allowed_tokens_fn(
                _answer_tokenizer,
                JsonSchemaParser(schema),
            )
        try:
            with INFERENCE_LOCK, torch.inference_mode():
                output = _answer.generate(**inputs.to("cuda"), **options)[0][input_length:]
            if len(output) >= max_new_tokens and int(output[-1]) != _answer_tokenizer.eos_token_id:
                raise LlmError("Generation reached its output limit; no verified synthesis is available.")
            content = _answer_tokenizer.decode(output, skip_special_tokens=True)
            if not isinstance(content, str) or not content.strip():
                raise LlmError("ZeroGPU returned an empty answer.")
            return content.strip()
        except (RuntimeError, ValueError) as exc:
            raise LlmError("ZeroGPU generation failed; no verified synthesis is available.") from exc

    def generate_json(self, schema: type[T], system: str, user: str) -> T:
        try:
            return schema.model_validate_json(self._complete(system, user, schema.model_json_schema()))
        except ValidationError as exc:
            raise LlmError("Model output failed the claim schema; no verified synthesis is available.") from exc

    def generate_text(self, system: str, user: str) -> str:
        return self._complete(system, user)


def embed_texts(texts: list[str]) -> list[list[float]]:
    import torch
    import torch.nn.functional as functional

    from app.retrieval.embed import EMBED_BATCH_SIZE, EMBED_DIMENSIONS, EmbeddingUnavailable

    if not ready():
        raise EmbeddingUnavailable("ZeroGPU embeddings are unavailable.")
    vectors = []
    try:
        for offset in range(0, len(texts), EMBED_BATCH_SIZE):
            inputs = _embedding_tokenizer(
                texts[offset : offset + EMBED_BATCH_SIZE],
                padding=True,
                truncation=True,
                max_length=2048,
                return_tensors="pt",
            ).to("cuda")
            with INFERENCE_LOCK, torch.inference_mode():
                hidden = _embedding(**inputs).last_hidden_state
                # Left padding ensures the last token is the final non-padding token.
                embeddings = functional.normalize(hidden[:, -1].float(), p=2, dim=1)
            if (
                embeddings.shape[1] != EMBED_DIMENSIONS
                or not torch.isfinite(embeddings).all()
                or not (embeddings.norm(dim=1) > 0).all()
            ):
                raise ValueError("Invalid embedding shape or values")
            vectors.extend(embeddings.cpu().tolist())
    except (RuntimeError, ValueError) as exc:
        raise EmbeddingUnavailable("ZeroGPU embedding inference failed.") from exc
    return vectors
