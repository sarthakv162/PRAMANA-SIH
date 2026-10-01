"""App settings, read from environment / .env. See .env.example for the full list."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


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

    llm_provider: str = Field(default="groq", alias="LLM_PROVIDER")
    llm_model: str = Field(default="openai/gpt-oss-120b", alias="LLM_MODEL")
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    llm_api_key: str = Field(default="", alias="LLM_API_KEY")

    embedder: str = Field(default="local", alias="EMBEDDER")
    embed_model: str = Field(default="BAAI/bge-m3", alias="EMBED_MODEL")

    rerank: bool = Field(default=False, alias="RERANK")
    rerank_skip_margin: float = Field(default=0.15, alias="RERANK_SKIP_MARGIN")

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
    confidence_w_retrieval_margin: float = Field(
        default=0.25, alias="CONFIDENCE_W_RETRIEVAL_MARGIN"
    )
    confidence_w_mean_entail: float = Field(default=0.25, alias="CONFIDENCE_W_MEAN_ENTAIL")
    confidence_w_verified_ratio: float = Field(default=0.25, alias="CONFIDENCE_W_VERIFIED_RATIO")
    confidence_w_back_translation: float = Field(
        default=0.25, alias="CONFIDENCE_W_BACK_TRANSLATION"
    )

    bhashini_user_id: str = Field(default="", alias="BHASHINI_USER_ID")
    bhashini_api_key: str = Field(default="", alias="BHASHINI_API_KEY")
    bhashini_pipeline_id: str = Field(default="", alias="BHASHINI_PIPELINE_ID")
    translate_provider: str = Field(default="llm", alias="TRANSLATE_PROVIDER")

    request_deadline_s: float = Field(default=45.0, alias="REQUEST_DEADLINE_S")

    rate_limit_requests: int = Field(default=120, alias="RATE_LIMIT_REQUESTS")
    rate_limit_window_s: int = Field(default=60, alias="RATE_LIMIT_WINDOW_S")

    mock_mode: bool = Field(default=True, alias="MOCK_MODE")
    demo_key: str = Field(default="", alias="DEMO_KEY")

    fixtures_dir: str = Field(default="../contracts/fixtures", alias="FIXTURES_DIR")


@lru_cache
def get_settings() -> Settings:
    return Settings()
