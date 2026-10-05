"""Adapter contract tests. Test doubles exercise validation, not GPU inference."""

from types import SimpleNamespace

import pytest

from app.config import Settings, answer_model_id, embedding_model_id
from app.generation import transformers_runtime as runtime
from app.generation.claim_schema import GenerationResult
from app.generation.llm import LlmError
from app.retrieval.embed import EmbeddingUnavailable


def test_real_schema_enforcement_allows_valid_claims_and_blocks_wrong_fields():
    pytest.importorskip("lmformatenforcer")
    import torch
    from tokenizers import Tokenizer, decoders, models, pre_tokenizers, trainers
    from transformers import PreTrainedTokenizerFast

    from app.generation.schema_tokens import schema_prefix, tokenizer_data

    backend = Tokenizer(models.BPE(unk_token="<unk>"))
    backend.pre_tokenizer = pre_tokenizers.ByteLevel(add_prefix_space=False)
    backend.decoder = decoders.ByteLevel()
    backend.train_from_iterator(
        ['{"claims":[{"statement":"Test statement","evidence_ids":["E1"]}],"gaps":[]}'],
        trainers.BpeTrainer(vocab_size=256, initial_alphabet=pre_tokenizers.ByteLevel.alphabet(),
                            special_tokens=["<eos>", "<unk>"]),
    )
    tokenizer = PreTrainedTokenizerFast(tokenizer_object=backend, eos_token="<eos>", unk_token="<unk>")
    data = tokenizer_data(tokenizer)

    def permitted(payload):
        prefix = schema_prefix(data, GenerationResult.model_json_schema())
        ids = tokenizer.encode("Prompt", add_special_tokens=False)
        for token in tokenizer.encode(payload, add_special_tokens=False):
            if token not in prefix(0, torch.tensor(ids)):
                return False
            ids.append(token)
        return tokenizer.eos_token_id in prefix(0, torch.tensor(ids))

    assert permitted('{"claims":[{"statement":"Test statement","evidence_ids":["E1"]}],"gaps":[]}')
    assert not permitted('{"claims":[{"status":"verified"}],"gaps":[]}')


def test_hosted_and_ollama_embedding_spaces_have_distinct_identity():
    hosted = Settings(INFERENCE_RUNTIME="transformers")
    local = Settings(INFERENCE_RUNTIME="ollama")
    assert answer_model_id(hosted) == "Qwen/Qwen3-4B"
    assert embedding_model_id(hosted) != embedding_model_id(local)


def test_uninitialized_models_cannot_claim_synthesis_or_embeddings(monkeypatch):
    monkeypatch.setattr(runtime, "_answer", None)
    with pytest.raises(LlmError, match="unavailable"):
        runtime.TransformersClient().generate_json(GenerationResult, "system", "question")
    with pytest.raises(EmbeddingUnavailable, match="unavailable"):
        runtime.embed_texts(["question"])


def test_generated_json_must_pass_original_claim_schema(monkeypatch):
    schema_seen = []

    def complete(self, system, user, schema):
        schema_seen.append(schema)
        return '{"claims":[{"statement":"Test statement","evidence_ids":["E1"]}],"gaps":[]}'

    monkeypatch.setattr(runtime.TransformersClient, "_complete", complete)
    result = runtime.TransformersClient().generate_json(GenerationResult, "system", "question")
    assert result.claims[0].evidence_ids == ["E1"]
    assert schema_seen == [GenerationResult.model_json_schema()]
    monkeypatch.setattr(runtime.TransformersClient, "_complete", lambda *args: '{"claims":[{"status":"verified"}]}')
    with pytest.raises(LlmError, match="schema"):
        runtime.TransformersClient().generate_json(GenerationResult, "system", "question")


def test_context_budget_rejects_excessive_input_before_generation(monkeypatch):
    tokenizer = SimpleNamespace(
        apply_chat_template=lambda *args, **kwargs: "test prompt",
        eos_token_id=1,
    )

    class Tokenizer:
        apply_chat_template = tokenizer.apply_chat_template
        eos_token_id = 1

        def __call__(self, *args, **kwargs):
            return {"input_ids": SimpleNamespace(shape=(1, 8190))}

    monkeypatch.setattr(runtime, "ready", lambda: True)
    monkeypatch.setattr(runtime, "_answer_tokenizer", Tokenizer())
    monkeypatch.setattr(runtime, "get_settings", lambda: Settings())
    with pytest.raises(LlmError, match="8K"):
        runtime.TransformersClient().generate_text("system", "question")


def test_queued_event_stream_retains_result_in_final_update(monkeypatch):
    from app.api.space_server import query_events
    from app.orchestrator import graph

    async def events(request):
        yield {"event": "result", "data": {"message": "Test card"}}
        yield {"event": "done", "data": {}}

    monkeypatch.setattr(graph, "run_query", events)
    updates = list(query_events('{"query":"Unit test query"}'))
    assert updates[-1]["event"] == "done" and updates[-1]["result"] == updates[0]["data"]
