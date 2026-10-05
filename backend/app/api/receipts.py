"""GET /v1/receipts/{id}, POST /v1/receipts/{id}/verify. See §5.3, §6.9."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.audit import receipts as receipts_store
from app.config import get_settings
from app.core.db import get_session
from app.core.fixtures import load_fixture
from app.schemas.receipts import Receipt, VerifyResult

router = APIRouter(tags=["receipts"])

# The tampered fixture demonstrates the failure path (§6.9's verify_tampered.json test); every
# other receipt id in mock mode verifies clean.
_TAMPERED_ID = "rcp_tampered_demo"


def _mock_receipt(receipt_id: str) -> Receipt | None:
    for fixture_name in (
        "answer_card_in.json",
        "answer_card_both_hi.json",
        "refusal_no_evidence.json",
        "refusal_legal_advice.json",
    ):
        payload = load_fixture(fixture_name)
        if payload.get("receipt_id") == receipt_id:
            receipt = Receipt.model_validate(load_fixture("receipt.json"))
            cited_spans = payload.get("evidence") or {span["id"]: span for span in payload.get("nearest_sources", [])}
            return receipt.model_copy(
                update={
                    "id": receipt_id,
                    "request_id": payload["request_id"],
                    "chunk_hashes": [span["sha256"] for span in cited_spans.values()],
                }
            )
    return None


@router.get("/receipts/{receipt_id}", response_model=Receipt)
async def get_receipt(receipt_id: str, session: Session = Depends(get_session)) -> Receipt:
    settings = get_settings()
    if settings.mock_mode:
        receipt = _mock_receipt(receipt_id)
        if receipt_id == _TAMPERED_ID:
            receipt = Receipt.model_validate(load_fixture("receipt.json")).model_copy(update={"id": _TAMPERED_ID})
        if receipt is None:
            raise HTTPException(status_code=404, detail="receipt not found")
        return receipt

    stored_receipt = receipts_store.get_receipt(session, receipt_id)
    if stored_receipt is None:
        raise HTTPException(status_code=404, detail="receipt not found")
    return stored_receipt


@router.post("/receipts/{receipt_id}/verify", response_model=VerifyResult)
async def verify_receipt(receipt_id: str, session: Session = Depends(get_session)) -> VerifyResult:
    settings = get_settings()
    if settings.mock_mode:
        fixture_name = "verify_tampered.json" if receipt_id == _TAMPERED_ID else "verify_ok.json"
        return VerifyResult.model_validate(load_fixture(fixture_name))

    result = receipts_store.verify_receipt(session, receipt_id)
    if result is None:
        raise HTTPException(status_code=404, detail="receipt not found")
    return result
