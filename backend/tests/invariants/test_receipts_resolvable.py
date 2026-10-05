"""Every response's `receipt_id` must actually resolve via `/receipts/{id}` (§6.9: "Per
response"). Before this fix, `classify`/`patent-risk`/`abs-check`/`tk-radar` minted random
`rcp_<hex>` strings that `audit/receipts.py::get_receipt` could never parse a sequence number
out of — this locks in the real, chained receipt those endpoints now write via
`audit/rule_receipts.py::record_rule_engine_result`.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.audit.receipts import get_receipt, latest_result_for_request, verify_receipt
from app.audit.rule_receipts import record_rule_engine_result
from app.rules.engine import resolve_citations


def test_rule_engine_receipt_resolves_and_verifies(db_session: Session, live_corpus_version: tuple[str, str]) -> None:
    cv_id, cv_label = live_corpus_version
    evidence, chunk_ids = resolve_citations(
        db_session, ["patents_act_1970#s3(p)"], cv_id, cv_label, ["IN"], date.today()
    )
    assert evidence, "expected patents_act_1970#s3(p) to be ingested for this test to mean anything"

    result_payload = {"type": "test_probe", "ok": True}
    receipt_id = record_rule_engine_result(
        db_session,
        corpus_version_id=cv_id,
        corpus_version_label=cv_label,
        endpoint="test_probe",
        jurisdiction="IN",
        as_of=date.today(),
        request_payload={"probe": True},
        evidence=evidence,
        chunk_id_by_evidence_id=chunk_ids,
        result_payload=result_payload,
    )

    receipt = get_receipt(db_session, receipt_id)
    assert receipt is not None
    assert receipt.corpus_version == cv_label
    assert receipt.model_ids.llm == "none"

    verify_result = verify_receipt(db_session, receipt_id)
    assert verify_result is not None
    assert verify_result.chain_valid
    assert verify_result.spans
    assert all(span.merkle_proof_valid for span in verify_result.spans)

    stored = latest_result_for_request(db_session, receipt.request_id)
    assert stored is not None
    assert stored.result == {**result_payload, "receipt_id": receipt_id}
    assert stored.request_payload == {"probe": True}


def test_random_receipt_ids_do_not_resolve(db_session: Session, live_corpus_version: tuple[str, str]) -> None:
    assert get_receipt(db_session, "rcp_deadbeefcafe") is None
    assert verify_receipt(db_session, "rcp_deadbeefcafe") is None


def test_latest_result_for_request_rejects_malformed_ids(
    db_session: Session, live_corpus_version: tuple[str, str]
) -> None:
    assert latest_result_for_request(db_session, "") is None
    assert latest_result_for_request(db_session, "not-a-uuid") is None
    assert latest_result_for_request(db_session, "00000000-0000-0000-0000-000000000000") is None


def test_saved_result_tampering_is_detected(db_session, live_corpus_version) -> None:
    import pytest
    import sqlalchemy as sa

    from app.core.errors import ApiError
    from app.history.service import get_result, results

    cv_id, cv_label = live_corpus_version
    receipt_id = record_rule_engine_result(
        db_session,
        corpus_version_id=cv_id,
        corpus_version_label=cv_label,
        endpoint="tamper_probe",
        jurisdiction="IN",
        as_of=date.today(),
        request_payload={},
        evidence={},
        chunk_id_by_evidence_id={},
        result_payload={"type": "probe", "message": "Original", "receipt_id": ""},
    )
    request_id = get_receipt(db_session, receipt_id).request_id
    assert get_result(db_session, request_id)["result"]["message"] == "Original"
    db_session.execute(
        sa.update(results)
        .where(results.c.request_id == request_id)
        .values(result={"type": "probe", "message": "Changed", "receipt_id": "rcp_invalid"})
    )
    db_session.commit()
    with pytest.raises(ApiError, match="integrity"):
        get_result(db_session, request_id)
