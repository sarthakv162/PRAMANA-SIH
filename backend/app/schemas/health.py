"""GET /v1/health response."""

from app.schemas.base import ContractModel


class ModelsStatus(ContractModel):
    llm: str
    embed: str
    nli: str
    llm_ready: bool = False
    embed_ready: bool = False
    nli_ready: bool = False


class HealthStatus(ContractModel):
    status: str = "ok"
    mock_mode: bool = True
    corpus_version: str
    models: ModelsStatus
    corpus_embedding_compatible: bool = False
    memory_budget_gb: int = 12
    speech_asr_available: bool = False
    public_demo_mode: bool = False
    inference_runtime: str = "ollama"
    storage_mode: str = "persistent"
    query_transport: str = "sse"
