from fastapi.testclient import TestClient

from app.api import escalations as escalations_api
from app.config import Settings
from app.main import app


def test_escalation_admin_requires_configured_demo_key(monkeypatch) -> None:
    monkeypatch.setattr(
        escalations_api,
        "get_settings",
        lambda: Settings(mock_mode=True, demo_key="test-secret"),
    )
    client = TestClient(app)
    assert client.get("/v1/escalations").status_code == 401
    assert client.get("/v1/escalations", headers={"X-Demo-Key": "wrong"}).status_code == 401
    response = client.get("/v1/escalations", headers={"X-Demo-Key": "test-secret"})
    assert response.status_code == 200


def test_escalation_admin_fails_closed_without_key(monkeypatch) -> None:
    monkeypatch.setattr(
        escalations_api,
        "get_settings",
        lambda: Settings(mock_mode=True, demo_key=""),
    )
    response = TestClient(app).get("/v1/escalations")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "admin_auth_not_configured"
