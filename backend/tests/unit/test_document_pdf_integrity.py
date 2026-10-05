from types import SimpleNamespace

import pytest

from app.api import documents
from app.core.hashing import sha256_hex


@pytest.mark.parametrize("valid", [True, False])
def test_pdf_is_served_only_when_it_matches_the_pinned_version(client, monkeypatch, tmp_path, valid):
    payload = b"%PDF-1.7\nunit-test-document"
    (tmp_path / "source.pdf").write_bytes(payload)
    monkeypatch.setattr(documents, "CORPUS_ROOT", tmp_path)
    monkeypatch.setattr(documents, "get_settings", lambda: SimpleNamespace(mock_mode=False))
    monkeypatch.setattr(documents.repo, "fetch_document_by_short_key", lambda *_args: SimpleNamespace(id="source"))
    monkeypatch.setattr(documents, "live_corpus_version", lambda _session: ("id", "pinned-test-version"))
    monkeypatch.setattr(documents.repo, "document_artifact", lambda *_args: {
        "pdf_path": "source.pdf", "file_sha256": sha256_hex(payload if valid else b"original-version"),
    })
    response = client.get("/v1/documents/source/pdf")
    if valid:
        assert response.status_code == 200 and response.content == payload
    else:
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "pdf_unavailable"
