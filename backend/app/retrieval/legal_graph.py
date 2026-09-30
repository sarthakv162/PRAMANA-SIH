"""Graph expansion for the resolve step (§6.4 `resolve`, §6.5 "graph expansion").

A retrieved chunk's *section* may have a proviso, explanation, definition, or amending
instrument attached via `edges`. Those are legally part of reading the section correctly (a
proviso silently ignored can flip a claim's meaning), so `resolve` pulls them in as extra
evidence — still gated through `retrieval/repo.py` so they obey the same jurisdiction/as-of
window as the chunk that triggered the expansion.
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
    """Return chunk IDs for sections reachable within `depth` hops of `defined_in`,
    `proviso_of`, `exception_to`, or `amends` edges from `section_ids`.
    """
    related_section_ids = repo.graph_expand(
        session,
        section_ids,
        corpus_version_id,
        kinds=("defined_in", "proviso_of", "exception_to", "amends"),
        depth=depth,
    )
    if not related_section_ids:
        return []
    rows = repo.fetch_chunks_for_sections(
        session, related_section_ids, corpus_version_id, jurisdictions, as_of
    )
    return [str(row.id) for row in rows]
