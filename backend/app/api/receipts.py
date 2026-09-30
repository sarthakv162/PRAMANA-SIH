"""GET /v1/receipts/{id}, POST /v1/receipts/{id}/verify. See §5.3, §6.9."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.core.errors import NotImplementedYet
from app.core.fixtures import load_fixture
from app.schemas.receipts import Receipt, VerifyResult

router = APIRouter(tags=["receipts"])

# The tampered fixture demonstrates the failure path (§6.9's verify_tampered.json test); every
# other receipt id in mock mode verifies clean.
_TAMPERED_ID = "rcp_tampered_demo"


@router.get("/receipts/{receipt_id}", response_model=Receipt)
async def get_receipt(receipt_id: str) -> Receipt:
    settings = get_settings()
    if not settings.mock_mode:
        raise NotImplementedYet("GET /receipts/{id}")
    receipt = Receipt.model_validate(load_fixture("receipt.json"))
    if receipt_id != receipt.id and receipt_id != _TAMPERED_ID:
        raise HTTPException(status_code=404, detail="receipt not found")
    if receipt_id == _TAMPERED_ID:
        receipt = receipt.model_copy(update={"id": _TAMPERED_ID})
    return receipt


@router.post("/receipts/{receipt_id}/verify", response_model=VerifyResult)
async def verify_receipt(receipt_id: str) -> VerifyResult:
    settings = get_settings()
    if not settings.mock_mode:
        raise NotImplementedYet("POST /receipts/{id}/verify")
    fixture_name = "verify_tampered.json" if receipt_id == _TAMPERED_ID else "verify_ok.json"
    return VerifyResult.model_validate(load_fixture(fixture_name))
