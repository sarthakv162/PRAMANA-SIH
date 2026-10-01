from fastapi.testclient import TestClient


def test_health_ok(client: TestClient) -> None:
    r = client.get("/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["mock_mode"] is True
    assert "corpus_version" in body
    assert set(body["models"]) == {"llm", "embed", "nli"}
