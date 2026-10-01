from concurrent.futures import ThreadPoolExecutor
from datetime import date

import sqlalchemy as sa

from app.audit.chain import audit_log, verify_chain_segment
from app.audit.rule_receipts import record_rule_engine_result
from app.core.db import SessionLocal


def test_concurrent_receipt_appends_leave_a_single_valid_chain(
    live_corpus_version: tuple[str, str],
) -> None:
    corpus_version_id, corpus_version_label = live_corpus_version

    def append(index: int) -> str:
        with SessionLocal() as session:
            return record_rule_engine_result(
                session,
                corpus_version_id=corpus_version_id,
                corpus_version_label=corpus_version_label,
                endpoint="concurrency_test",
                jurisdiction="IN",
                as_of=date.today(),
                request_payload={"probe": index},
                evidence={},
                chunk_id_by_evidence_id={},
                result_payload={"probe": index},
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        receipt_ids = list(pool.map(append, (1, 2)))
    assert len(set(receipt_ids)) == 2

    with SessionLocal() as session:
        last_seq = session.execute(sa.select(sa.func.max(audit_log.c.seq))).scalar_one()
        assert last_seq is not None
        assert verify_chain_segment(session, int(last_seq))
