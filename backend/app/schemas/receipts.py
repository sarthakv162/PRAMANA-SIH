"""Receipt / VerifyResult — audit chain + Merkle proofs. See §5.2, §6.9."""

from datetime import datetime

from pydantic import Field

from app.schemas.base import ContractModel


class ModelIds(ContractModel):
    llm: str
    embed: str
    nli: str


class Receipt(ContractModel):
    id: str
    request_id: str
    corpus_version: str
    query_hash: str
    chunk_hashes: list[str]
    model_ids: ModelIds
    prompt_version: str
    prev_hash: str
    entry_hash: str
    created_at: datetime


class SpanVerification(ContractModel):
    evidence_id: str
    sha256: str
    in_corpus: bool
    merkle_proof_valid: bool


class VerifyResult(ContractModel):
    chain_valid: bool
    corpus_root: str
    spans: list[SpanVerification] = Field(default_factory=list)
