from datetime import date
from unittest.mock import patch

from app.retrieval.legal_graph import attach_related_chunks


def test_related_chunks_include_parent_context_and_graph_edges() -> None:
    rows = [type("Chunk", (), {"id": "parent-chunk"})(), type("Chunk", (), {"id": "related-chunk"})()]
    with (
        patch("app.retrieval.legal_graph.repo.ancestor_section_ids", return_value=["parent"]),
        patch("app.retrieval.legal_graph.repo.graph_expand", return_value=["related"]),
        patch(
            "app.retrieval.legal_graph.repo.fetch_chunks_for_sections", return_value=rows
        ) as fetch_chunks,
    ):
        chunk_ids = attach_related_chunks(
            object(), ["clause"], "corpus", ["IN"], date(2026, 1, 1)
        )

    assert chunk_ids == ["parent-chunk", "related-chunk"]
    assert fetch_chunks.call_args.args[1] == ["parent", "related"]
