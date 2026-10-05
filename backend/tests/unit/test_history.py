from datetime import timedelta
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api import conversations as endpoints
from app.core.db import get_session
from app.core.errors import ApiError
from app.history import service
from app.main import app


@pytest.fixture
def db(monkeypatch):
    engine = sa.create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
    service.metadata.create_all(engine)
    monkeypatch.setattr(service, "get_settings", lambda: SimpleNamespace(workspace_id="shared-demo"))
    with Session(engine) as session:
        yield session
    engine.dispose()


def test_history_survives_session_reload_scrubs_and_has_followup_context(db):
    conversation = service.create_conversation(db, "Email test@example.com")
    service.add_user_message(db, conversation["id"], "My phone 9876543210; can TK be patented?", "req-one")
    service.save_result(
        db,
        "req-one",
        {"type": "refusal", "message": "No synthesis", "receipt_id": ""},
        "rcp_1",
        "hash",
        conversation_id=conversation["id"],
    )
    db.commit()
    with Session(db.get_bind()) as reloaded:
        saved = service.conversation_detail(reloaded, conversation["id"])
        assert len(saved["messages"]) == 2
        assert "test@example.com" not in saved["title"]
        assert "9876543210" not in saved["messages"][0]["content"]
        assert "TK" in service.recent_context(reloaded, conversation["id"])
        assert saved["messages"][1]["result"]["receipt_id"] == "rcp_1"


def test_expiry_deletes_results_messages_and_case_references(db):
    conversation = service.create_conversation(db, "Topic")
    service.add_user_message(db, conversation["id"], "Question", "req-one")
    service.save_result(db, "req-one", {"message": "Saved result"}, "rcp_1", "hash", conversation_id=conversation["id"])
    db.commit()
    service.add_case_ref(db, "req-one")
    old = service._now() - timedelta(days=31)
    for table in [service.conversations, service.messages, service.results]:
        db.execute(sa.update(table).values(expires_at=old))
    db.commit()
    service.purge_expired(db)
    assert service.list_conversations(db) == [] and service.list_case_refs(db) == []
    with pytest.raises(ApiError):
        service.get_result(db, "req-one")


def test_workspace_boundary_and_shared_access(db, monkeypatch):
    conversation = service.create_conversation(db, "Topic")
    monkeypatch.setattr(service, "get_settings", lambda: SimpleNamespace(workspace_id="different-workspace"))
    assert service.list_conversations(db) == []
    with pytest.raises(ApiError):
        service.require_conversation(db, conversation["id"])


def test_conversation_endpoints_auth_list_resume_delete(db, monkeypatch):
    monkeypatch.setattr(endpoints, "get_settings", lambda: SimpleNamespace(demo_key="test-key", public_demo_mode=False))
    app.dependency_overrides[get_session] = lambda: db
    try:
        client = TestClient(app)
        assert client.get("/v1/conversations").status_code == 401
        headers = {"X-Demo-Key": "test-key"}
        created = client.post("/v1/conversations", headers=headers, json={"title": "New topic"})
        assert created.status_code == 201
        id = created.json()["id"]
        assert len(client.get("/v1/conversations", headers=headers).json()) == 1
        assert client.get(f"/v1/conversations/{id}", headers=headers).status_code == 200
        assert client.delete(f"/v1/conversations/{id}", headers=headers).status_code == 204
        assert client.get(f"/v1/conversations/{id}", headers=headers).status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_public_demo_history_needs_no_key_and_is_shared(db, monkeypatch):
    monkeypatch.setattr(endpoints, "get_settings", lambda: SimpleNamespace(demo_key="", public_demo_mode=True))
    app.dependency_overrides[get_session] = lambda: db
    try:
        first = TestClient(app)
        second = TestClient(app)
        created = first.post("/v1/conversations", json={"title": "Public judging demo"})
        assert created.status_code == 201
        conversation_id = created.json()["id"]
        assert second.get("/v1/conversations").json()[0]["id"] == conversation_id
        assert second.get(f"/v1/conversations/{conversation_id}").status_code == 200
        assert second.delete(f"/v1/conversations/{conversation_id}").status_code == 204
        assert first.get("/v1/conversations").json() == []
    finally:
        app.dependency_overrides.clear()


def test_private_workspace_without_key_stays_unavailable(monkeypatch):
    monkeypatch.setattr(endpoints, "get_settings", lambda: SimpleNamespace(demo_key="", public_demo_mode=False))
    with pytest.raises(ApiError) as error:
        endpoints.authorize_workspace("")
    assert error.value.code == "workspace_not_configured"
