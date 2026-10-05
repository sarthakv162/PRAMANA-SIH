"""Storage invariants for the ephemeral demo, using explicitly synthetic test rows."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.audit.chain import audit_log, verify_chain_segment
from app.audit.merkle import merkle_root
from app.audit.receipts import build_receipt, get_receipt, verify_receipt
from app.config import get_settings
from app.core.errors import ApiError
from app.core.hashing import sha256_hex
from app.core.portable import populate_snapshot, restore_snapshot
from app.history import service
from app.orchestrator.nodes.intake import requests_table
from app.retrieval import repo
from app.retrieval.evidence_pack import build_evidence_pack
from app.schemas.receipts import ModelIds


@pytest.fixture
def portable(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "storage_mode", "ephemeral")
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'demo.sqlite'}", connect_args={"timeout": 30})
    version, doc, section, chunk = [uuid.uuid4() for _ in range(4)]
    text = "Traditional knowledge is not an invention under this test provision."
    digest = sha256_hex(text)
    data = {
        "corpus_versions": [
            {
                "id": version,
                "label": "unit-test",
                "status": "live",
                "merkle_root": merkle_root([digest]),
                "created_at": datetime.now(UTC),
                "embedding_model": "unit-test",
            }
        ],
        "documents": [
            {
                "id": doc,
                "short_key": "test-law",
                "title": "Test provision",
                "doc_type": "statute",
                "jurisdiction": "IN",
                "issuer": "test",
                "language": "en",
                "source_url": "https://example.org/test",
            }
        ],
        "sections": [
            {
                "id": section,
                "document_id": doc,
                "corpus_version_id": version,
                "section_key": "test-law#s1",
                "path": ["1"],
                "heading": "Test provision",
                "text": text,
                "sha256": digest,
            }
        ],
        "chunks": [
            {
                "id": chunk,
                "section_id": section,
                "corpus_version_id": version,
                "jurisdiction": "IN",
                "doc_type": "statute",
                "effective_from": date(2020, 1, 1),
                "effective_to": date(2030, 1, 1),
                "page": 1,
                "char_start": 0,
                "char_end": len(text),
                "text": text,
                "sha256": digest,
                "bboxes": [{"page": 1, "page_width": 600, "page_height": 800, "rects": [[60, 80, 540, 160]]}],
            }
        ],
        "edges": [],
        "document_versions": [],
    }
    populate_snapshot(engine, data)
    yield engine, str(version), str(chunk)
    engine.dispose()


def test_real_fts_obeys_all_legal_filters_and_portable_ids(portable):
    engine, version, chunk = portable
    with Session(engine) as session:
        found = repo.keyword_search(session, version, ["IN"], date(2026, 1, 1), "traditional knowledge")
        assert str(found[0][0].id) == chunk and found[0][1] > 0
        for jurisdictions, as_of, keys in [
            (["INTL"], date(2026, 1, 1), None),
            (["IN"], date(2019, 1, 1), None),
            (["IN"], date(2030, 1, 1), None),
            (["IN"], date(2026, 1, 1), ["different-law"]),
        ]:
            assert not repo.keyword_search(session, version, jurisdictions, as_of, "knowledge", doc_keys=keys)


def test_corpus_and_audit_are_immutable(portable):
    engine, version, _ = portable
    with engine.begin() as connection, pytest.raises(sa.exc.IntegrityError, match="immutable"):
        connection.execute(
            sa.update(repo.corpus_versions).where(repo.corpus_versions.c.id == version).values(status="staged")
        )


def write_receipt(engine, version, chunk, conversation_id=None):
    request_id = str(uuid.uuid4())
    with Session(engine) as session:
        session.execute(requests_table.insert().values(id=request_id, corpus_version_id=version))
        rows = repo.fetch_chunks_by_ids(session, [chunk], version, ["IN"], date(2026, 1, 1))
        evidence = build_evidence_pack(session, rows, "unit-test")
        receipt = build_receipt(
            session,
            request_id,
            "unit-test",
            sha256_hex("query"),
            evidence,
            ModelIds(llm="none", embed="none", nli="none"),
            "unit-test",
            {"message": "Stored test result", "receipt_id": ""},
            conversation_id=conversation_id,
        )
        return request_id, receipt.id


def test_saved_history_receipts_and_tamper_checks_survive_new_connection(portable):
    engine, version, chunk = portable
    with Session(engine) as session:
        conversation = service.create_conversation(session, "Reach me at test@example.com")
    request_id, receipt_id = write_receipt(engine, version, chunk, conversation["id"])
    with Session(engine) as session:
        assert "test@example.com" not in service.conversation_detail(session, conversation["id"])["title"]
        assert service.get_result(session, request_id)["receipt_id"] == receipt_id
        assert get_receipt(session, receipt_id).request_id == request_id
        proof = verify_receipt(session, receipt_id)
        assert proof.chain_valid and all(span.merkle_proof_valid for span in proof.spans)
        session.execute(
            service.results.update()
            .where(service.results.c.request_id == request_id)
            .values(result={"message": "Tampered"})
        )
        session.commit()
        with pytest.raises(ApiError, match="integrity"):
            service.get_result(session, request_id)
        with pytest.raises(sa.exc.IntegrityError, match="append only"):
            session.execute(audit_log.delete())


def test_concurrent_writers_keep_one_chain(portable):
    engine, version, chunk = portable
    with ThreadPoolExecutor(max_workers=3) as pool:
        receipts = list(pool.map(lambda _: write_receipt(engine, version, chunk), range(6)))
    assert len({receipt for _, receipt in receipts}) == 6
    with Session(engine) as session:
        assert verify_chain_segment(session, 6)


def test_restart_restores_empty_history_and_checksum_is_required(portable, tmp_path):
    import shutil

    engine, _, _ = portable
    seed = tmp_path / "pristine.sqlite"
    shutil.copyfile(tmp_path / "demo.sqlite", seed)
    with Session(engine) as session:
        service.create_conversation(session, "Temporary")
    destination = tmp_path / "restored.sqlite"
    with pytest.raises(ValueError, match="checksum"):
        restore_snapshot(seed, destination, "bad")
    # A separate pristine corpus seed is used at startup, not the runtime DB with chats.
    restore_snapshot(seed, destination, sha256_hex(seed.read_bytes()))
    assert destination.read_bytes() == seed.read_bytes()
    restored = sa.create_engine(f"sqlite:///{destination}")
    with Session(restored) as session:
        assert service.list_conversations(session) == []
        assert repo.live_corpus_version(session)[1] == "unit-test"
    restored.dispose()


def test_receipt_urls_from_previous_boot_cannot_resolve_to_new_answers(portable, monkeypatch):
    engine, version, chunk = portable
    _, old_receipt = write_receipt(engine, version, chunk)
    monkeypatch.setattr(get_settings(), "receipt_namespace", "000000000001")
    with Session(engine) as session:
        assert get_receipt(session, old_receipt) is None
        assert verify_receipt(session, old_receipt) is None
    _, new_receipt = write_receipt(engine, version, chunk)
    assert old_receipt != new_receipt
