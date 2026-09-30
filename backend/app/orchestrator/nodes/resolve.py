"""§6.4 `resolve`: materialise the ranked chunk rows into a numbered, citable evidence pack."""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.orchestrator.state import RequestState
from app.retrieval.evidence_pack import build_evidence_pack


def run(session: Session, state: RequestState, chunk_rows: list[sa.Row[Any]]) -> None:
    state.evidence_pack = build_evidence_pack(session, chunk_rows, state.corpus_version_label)
