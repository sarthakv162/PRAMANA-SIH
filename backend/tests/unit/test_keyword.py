from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock

from app.retrieval import keyword


def test_full_text_precedence_does_not_compare_unrelated_score_scales(monkeypatch):
    monkeypatch.setattr(keyword.repo, "keyword_search", lambda *args: [(SimpleNamespace(id="statute"), 0.001)])
    monkeypatch.setattr(keyword.repo, "trigram_search", lambda *args, **kwargs: [(SimpleNamespace(id="heading"), 0.8)])
    result = keyword.keyword_search(Mock(), "version", ["IN"], date.today(), "question")
    assert [key for key, _ in result] == ["statute", "heading"]
