"""§6.4 `retrieve` + §6.5: hybrid dense+keyword search, or a direct-citation fast path when
`route` already resolved an exact section. Either way, results are graph-expanded (1-hop
provisos/definitions/exceptions) before being handed to `resolve`.
"""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.orchestrator.state import RequestState
from app.retrieval import legal_graph, repo, rrf


def run(session: Session, state: RequestState) -> list[sa.Row[Any]]:
    if state.direct_section_key:
        section = repo.fetch_section_by_key(
            session, state.direct_section_key, state.corpus_version_id
        )
        if section is not None:
            chunk_ids = [
                str(row.id)
                for row in repo.fetch_chunks_for_section(
                    session, str(section.id), state.corpus_version_id
                )
            ]
            state.retrieval_margin = 1.0  # a resolved citation is unambiguous
        else:
            chunk_ids = []
    else:
        candidates = rrf.hybrid_retrieve(
            session,
            state.corpus_version_id,
            state.jurisdictions,
            state.as_of,
            state.query_en,
        )
        state.retrieval_margin = rrf.top1_top2_margin(candidates)
        chunk_ids = [c.chunk_id for c in candidates]

    if not chunk_ids:
        return []

    rows = repo.fetch_chunks_by_ids(
        session, chunk_ids, state.corpus_version_id, state.jurisdictions, state.as_of
    )
    section_ids = list({str(r.section_id) for r in rows})
    related_ids = legal_graph.attach_related_chunks(
        session, section_ids, state.corpus_version_id, state.jurisdictions, state.as_of
    )
    if related_ids:
        rows = rows + repo.fetch_chunks_by_ids(
            session, related_ids, state.corpus_version_id, state.jurisdictions, state.as_of
        )
    return rows
