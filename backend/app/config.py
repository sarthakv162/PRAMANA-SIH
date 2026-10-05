"""App settings, read from environment / .env. See .env.example for the full list."""

from functools import lru_cache
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_PROJECT_ROOT / ".env", extra="ignore")

    database_url: str = Field(
        default="postgresql+psycopg://pramana_app:local-dev-app@localhost:5432/pramana",
        alias="DATABASE_URL",
    )
    database_url_admin: str = Field(default="", alias="DATABASE_URL_ADMIN")
    ingest_database_url: str = Field(default="", alias="INGEST_DATABASE_URL")
    app_db_password: str = Field(default="", alias="APP_DB_PASSWORD")
    ingest_db_password: str = Field(default="", alias="INGEST_DB_PASSWORD")

    inference_runtime: Literal["ollama", "transformers"] = Field(default="ollama", alias="INFERENCE_RUNTIME")
    storage_mode: Literal["persistent", "ephemeral"] = Field(default="persistent", alias="STORAGE_MODE")
    query_transport: Literal["sse", "gradio"] = Field(default="sse", alias="QUERY_TRANSPORT")
    receipt_namespace: str = Field(
        default_factory=lambda: uuid4().hex[:12], pattern=r"^[a-f0-9]{12}$", alias="RECEIPT_NAMESPACE"
    )

    llm_model: Literal["qwen3:4b"] = Field(default="qwen3:4b", alias="LLM_MODEL")
    ollama_base_url: str = Field(default="http://127.0.0.1:11434", alias="OLLAMA_BASE_URL")
    ollama_context_tokens: int = Field(default=8192, ge=1024, le=8192, alias="OLLAMA_CONTEXT_TOKENS")
    ollama_keep_alive: str = Field(default="5m", alias="OLLAMA_KEEP_ALIVE")
    ollama_num_threads: int | None = Field(default=None, ge=1, le=64, alias="OLLAMA_NUM_THREADS")
    memory_budget_gb: int = Field(default=12, ge=12, le=12, alias="MEMORY_BUDGET_GB")
    workspace_id: str = Field(default="shared-demo", alias="WORKSPACE_ID")
    history_retention_days: int = Field(default=30, ge=30, le=30, alias="HISTORY_RETENTION_DAYS")

    @field_validator("ollama_base_url")
    @classmethod
    def local_ollama_only(cls, value: str) -> str:
        from urllib.parse import urlparse

        parsed = urlparse(value)
        if (
            parsed.scheme != "http"
            or parsed.hostname not in {"127.0.0.1", "localhost", "::1", "host.docker.internal", "ollama"}
            or (parsed.hostname == "ollama" and (parsed.port != 11434 or parsed.path not in {"", "/"}))
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("OLLAMA_BASE_URL must point to local Ollama or the same-server ollama:11434 service")
        return value.rstrip("/")

    embed_model: Literal["qwen3-embedding:0.6b"] = Field(default="qwen3-embedding:0.6b", alias="EMBED_MODEL")

    rerank: Literal[False] = Field(default=False, alias="RERANK")
    rerank_skip_margin: float = Field(default=0.15, alias="RERANK_SKIP_MARGIN")

    @field_validator("rerank", mode="before")
    @classmethod
    def disabled_reranker(cls, value: object) -> bool:
        if value is False or value in ("0", "false", "False", "off"):
            return False
        raise ValueError("Reranking is disabled in the 12 GB local model budget")

    nli_model: str = Field(
        default="MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7",
        alias="NLI_MODEL",
    )
    nli_tau_high: float = Field(default=0.80, alias="NLI_TAU_HIGH")
    nli_tau_low: float = Field(default=0.50, alias="NLI_TAU_LOW")

    tau_abstain: float = Field(default=0.35, alias="TAU_ABSTAIN")
    tau_review: float = Field(default=0.60, alias="TAU_REVIEW")

    # Confidence score weights (§6.7): retrieval margin, mean NLI entailment, verified-claim
    # ratio, back-translation health. Must sum to 1.0; picked as an even split until the
    # dev-set risk-coverage curve (§9) tunes them.
    confidence_w_retrieval_margin: float = Field(default=0.25, alias="CONFIDENCE_W_RETRIEVAL_MARGIN")
    confidence_w_mean_entail: float = Field(default=0.25, alias="CONFIDENCE_W_MEAN_ENTAIL")
    confidence_w_verified_ratio: float = Field(default=0.25, alias="CONFIDENCE_W_VERIFIED_RATIO")
    confidence_w_back_translation: float = Field(default=0.25, alias="CONFIDENCE_W_BACK_TRANSLATION")

    translate_provider: Literal["llm"] = Field(default="llm", alias="TRANSLATE_PROVIDER")

    # User-requested cloud speech exception. Text generation/translation remain local.
    sarvam_api_key: SecretStr = Field(default=SecretStr(""), alias="SARVAM_API_KEY")
    sarvam_tts_model: Literal["bulbul:v3"] = Field(default="bulbul:v3", alias="SARVAM_TTS_MODEL")
    sarvam_tts_speaker: str = Field(default="shubh", pattern=r"^[a-z]+$", alias="SARVAM_TTS_SPEAKER")
    sarvam_tts_timeout_s: float = Field(default=60.0, gt=0, le=120, alias="SARVAM_TTS_TIMEOUT_S")

    request_deadline_s: float = Field(default=180.0, alias="REQUEST_DEADLINE_S")

    rate_limit_requests: int = Field(default=120, alias="RATE_LIMIT_REQUESTS")
    rate_limit_window_s: int = Field(default=60, alias="RATE_LIMIT_WINDOW_S")

    mock_mode: bool = Field(default=False, alias="MOCK_MODE")
    public_demo_mode: bool = Field(default=False, alias="PUBLIC_DEMO_MODE")
    demo_key: str = Field(default="", alias="DEMO_KEY")

    fixtures_dir: str = Field(default="../contracts/fixtures", alias="FIXTURES_DIR")


@lru_cache
def get_settings() -> Settings:
    return Settings()


def answer_model_id(settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    return "Qwen/Qwen3-4B" if getattr(settings, "inference_runtime", "ollama") == "transformers" else settings.llm_model


def embedding_model_id(settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    return (
        "Qwen/Qwen3-Embedding-0.6B"
        if getattr(settings, "inference_runtime", "ollama") == "transformers"
        else settings.embed_model
    )
