from fastapi.testclient import TestClient


def test_health_ok(client: TestClient) -> None:
    r = client.get("/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["mock_mode"] is True
    assert "corpus_version" in body
    assert {"llm", "embed", "nli"} <= set(body["models"])
    assert body["public_demo_mode"] is False


def test_health_reports_actual_public_demo_setting(client, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "public_demo_mode", True)
    assert client.get("/v1/health").json()["public_demo_mode"] is True
