"""§6.4 `audit` + §6.9: writes the hash-chain entry, returns the receipt id embedded in the
rendered card.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.audit.receipts import build_receipt
from app.config import get_settings
from app.generation.prompts import PROMPT_VERSION
from app.orchestrator.state import RequestState
from app.retrieval.evidence_pack import NumberedSpan
from app.schemas.receipts import ModelIds


def run(session: Session, state: RequestState, result_payload: dict[str, Any]) -> str:
    settings = get_settings()
    receipt = build_receipt(
        session,
        request_id=state.request_id,
        corpus_version_label=state.corpus_version_label,
        query_hash=state.query_hash,
        cited_spans=[item for item in state.evidence_pack if _cited(item, result_payload)],
        model_ids=ModelIds(
            llm=settings.llm_model, embed=settings.embed_model, nli=settings.nli_model
        ),
        prompt_version=PROMPT_VERSION,
        result_payload=result_payload,
    )
    return receipt.id


def _cited(item: NumberedSpan, result_payload: dict[str, Any]) -> bool:
    """Only spans actually referenced in the rendered card go in the receipt — not every
    span retrieval considered.
    """
    evidence = result_payload.get("evidence") or {}
    nearest = {s.get("id") for s in result_payload.get("nearest_sources", [])}
    return item.evidence_id in evidence or item.evidence_id in nearest
