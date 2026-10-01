"""GET /v1/health response."""

from app.schemas.base import ContractModel


class ModelsStatus(ContractModel):
    llm: str
    embed: str
    nli: str


class HealthStatus(ContractModel):
    status: str = "ok"
    mock_mode: bool = True
    corpus_version: str
    models: ModelsStatus
