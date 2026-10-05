from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy.dialects import postgresql

from app.orchestrator.nodes import retrieve
from app.orchestrator.state import RequestState
from app.retrieval.coverage import requested_sources
from app.retrieval.repo import retrievable_chunks
from app.schemas.query import QueryRequest


@pytest.mark.parametrize(
    "name,key",
    [
        ("Patent Cooperation Treaty", "pct_treaty"),
        ("PCT", "pct_treaty"),
        ("Cosmetics Rules, 2020", "cosmetics_rules_2020"),
        ("Copyright Act", "copyright_act_1957"),
        ("Nagoya Protocol", "nagoya_protocol"),
        ("Patents Act, 1970", "patents_act_1970"),
    ],
)
def test_explicit_instrument_names(name, key):
    assert requested_sources(f"What does {name} say?") == {key}


def test_general_cosmetics_subject_does_not_require_unindexed_rules():
    assert requested_sources("What is a cosmetic product?") == set()


def test_missing_named_instrument_abstains_before_related_search(monkeypatch):
    monkeypatch.setattr(
        retrieve.repo, "documents_for_version", lambda *_: [SimpleNamespace(short_key="patents_act_1970")]
    )
    search = Mock(side_effect=AssertionError("Unrelated search must not run"))
    monkeypatch.setattr(retrieve.rrf, "hybrid_retrieve", search)
    request = QueryRequest(query="What does the Patent Cooperation Treaty say?")
    state = RequestState(
        request_id="test", raw_query=request.query, request=request, query_en=request.query, corpus_version_id="live"
    )
    assert retrieve.run(Mock(), state) == []
    search.assert_not_called()


def test_instrument_filter_is_applied_before_ranking():
    statement = retrievable_chunks("version", ["INTL"], date.today(), doc_keys=["nagoya_protocol"])
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "documents.short_key IN" in sql
    assert "corpus_version_id" in sql
    assert "effective_to" in sql


def test_available_instrument_constrains_hybrid_search(monkeypatch):
    monkeypatch.setattr(
        retrieve.repo, "documents_for_version", lambda *_: [SimpleNamespace(short_key="nagoya_protocol")]
    )
    search = Mock(return_value=[])
    monkeypatch.setattr(retrieve.rrf, "hybrid_retrieve", search)
    request = QueryRequest(query="Explain Nagoya Protocol consent requirements.")
    state = RequestState(
        request_id="test", raw_query=request.query, request=request, query_en=request.query, corpus_version_id="live"
    )
    assert retrieve.run(Mock(), state) == []
    assert search.call_args.kwargs["doc_keys"] == ["nagoya_protocol"]
