from fastapi.testclient import TestClient

from app.api import dossier as dossier_api
from app.api import query as query_api
from app.config import Settings
from app.main import app


def test_mock_query_selects_answer_and_refusal_fixtures(monkeypatch) -> None:
    from app.schemas.enums import Jurisdiction
    from app.schemas.query import QueryRequest

    monkeypatch.setattr(query_api, "get_settings", lambda: Settings(mock_mode=True))

    answer = QueryRequest(query="Can traditional knowledge be patented?", jurisdiction=Jurisdiction.IN)
    refusal = QueryRequest(query="What fees are listed?", jurisdiction=Jurisdiction.IN)
    legal_advice = QueryRequest(query="Should I file this patent?", jurisdiction=Jurisdiction.IN)
    both = QueryRequest(query="Can traditional knowledge be patented?", jurisdiction=Jurisdiction.BOTH)

    assert query_api._mock_result_name(answer) == "answer_card_in.json"
    assert query_api._mock_result_name(refusal) == "refusal_no_evidence.json"
    assert query_api._mock_result_name(legal_advice) == "refusal_legal_advice.json"
    assert query_api._mock_result_name(both) == "answer_card_both_hi.json"


def test_mock_dossier_returns_real_format_bytes_and_fixture_content(monkeypatch) -> None:
    monkeypatch.setattr(dossier_api, "get_settings", lambda: Settings(mock_mode=True))
    client = TestClient(app)
    item_id = "req_01JATNKQ3P0000000000IN01"

    markdown = client.post("/v1/dossier", json={"items": [item_id], "format": "md", "language": "en"})
    assert markdown.status_code == 200
    assert markdown.headers["content-type"].startswith("text/markdown")
    assert b"Patents Act, 1970" in markdown.content

    pdf = client.post("/v1/dossier", json={"items": [item_id], "format": "pdf", "language": "en"})
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF-")

    docx = client.post("/v1/dossier", json={"items": [item_id], "format": "docx", "language": "en"})
    assert docx.status_code == 200
    assert docx.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert docx.content.startswith(b"PK\x03\x04")
