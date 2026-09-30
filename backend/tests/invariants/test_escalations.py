"""`app/escalations.py` — an escalation must point at a real `requests` row (the FK a client
can't fake by supplying an arbitrary string), and a malformed id must 400/404 rather than
reach Postgres as a raw invalid-UUID DB error.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.orm import Session

from app.audit.rule_receipts import record_rule_engine_result
from app.core.errors import ApiError
from app.escalations import create_escalation, list_escalations
from app.schemas.misc import EscalationRequest


def _make_request_id(db_session: Session, live_corpus_version: tuple[str, str]) -> str:
    cv_id, cv_label = live_corpus_version
    receipt_id = record_rule_engine_result(
        db_session,
        corpus_version_id=cv_id,
        corpus_version_label=cv_label,
        endpoint="test_probe",
        jurisdiction="IN",
        as_of=date.today(),
        request_payload={"probe": True},
        evidence={},
        chunk_id_by_evidence_id={},
        result_payload={"type": "test_probe"},
    )
    from app.audit.receipts import get_receipt

    receipt = get_receipt(db_session, receipt_id)
    assert receipt is not None
    return receipt.request_id


def test_escalation_round_trips_for_a_real_request(
    db_session: Session, live_corpus_version: tuple[str, str]
) -> None:
    request_id = _make_request_id(db_session, live_corpus_version)
    response = create_escalation(
        db_session, EscalationRequest(request_id=request_id, contact="vaidya@example.com")
    )
    assert response.ticket_id.startswith("tkt_")
    assert response.status == "open"

    tickets = list_escalations(db_session)
    assert any(t["ticket_id"] == response.ticket_id and t["request_id"] == request_id for t in tickets)


def test_escalation_rejects_malformed_request_id(
    db_session: Session, live_corpus_version: tuple[str, str]
) -> None:
    with pytest.raises(ApiError) as exc_info:
        create_escalation(db_session, EscalationRequest(request_id="not-a-uuid"))
    assert exc_info.value.status_code == 400


def test_escalation_rejects_unknown_request_id(
    db_session: Session, live_corpus_version: tuple[str, str]
) -> None:
    with pytest.raises(ApiError) as exc_info:
        create_escalation(
            db_session, EscalationRequest(request_id="00000000-0000-0000-0000-000000000000")
        )
    assert exc_info.value.status_code == 404
