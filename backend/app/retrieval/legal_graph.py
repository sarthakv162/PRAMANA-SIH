"""Graph expansion for the resolve step (§6.4 `resolve`, §6.5 "graph expansion").

A retrieved clause/subsection may omit its parent section's introductory language, and a
section may also have a proviso, explanation, definition, or amending instrument attached via
`edges`. These are legally part of reading the text correctly, so retrieval adds parent
sections and graph-related chunks as extra evidence — still gated through `retrieval/repo.py`
so they obey the same jurisdiction/as-of window as the retrieved chunk.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.retrieval import repo


def attach_related_chunks(
    session: Session,
    section_ids: list[str],
    corpus_version_id: str,
    jurisdictions: list[str],
    as_of: date,
    depth: int = 1,
) -> list[str]:
    """Return parent-context and related chunk IDs for retrieved sections.

    Parent traversal supplies headings omitted by clause-level chunks; legal graph edges
    supply definitions, provisos, exceptions, and amending instruments.
    """
    parent_section_ids = repo.ancestor_section_ids(session, section_ids, corpus_version_id, max_depth=max(4, depth))
    graph_section_ids = repo.graph_expand(
        session,
        section_ids,
        corpus_version_id,
        kinds=("defined_in", "proviso_of", "exception_to", "amends"),
        depth=depth,
    )
    related_section_ids = sorted(set(parent_section_ids) | set(graph_section_ids))
    if not related_section_ids:
        return []
    rows = repo.fetch_chunks_for_sections(session, related_section_ids, corpus_version_id, jurisdictions, as_of)
    return [str(row.id) for row in rows]
