"""Regression test for a real-mode `/query` outage: `orchestrator/graph.py` used to mint
`request_id = f"req_{uuid.uuid4().hex[:20]}"`, but `orchestrator/nodes/intake.py` inserts it
into `requests.id`, a `uuid` column, via `uuid.UUID(state.request_id)` — a prefixed, truncated
hex string isn't valid UUID input, so every real (non-mock) `/query` call raised
`ValueError: badly formed hexadecimal UUID string` inside the `intake` stage. Fixed by minting
a plain `str(uuid.uuid4())`; this test exercises `intake.run` exactly as `run_query` calls it
and asserts the `requests` row insert succeeds.
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.orchestrator.nodes import intake
from app.orchestrator.state import RequestState
from app.schemas.enums import Jurisdiction
from app.schemas.query import QueryRequest


def test_graph_style_request_id_is_a_valid_uuid_intake_accepts(
    db_session: Session, live_corpus_version: tuple[str, str]
) -> None:
    request_id = str(uuid.uuid4())  # mirrors orchestrator/graph.py::run_query verbatim
    state = RequestState(
        request_id=request_id,
        raw_query="does traditional knowledge bar patenting under section 3(p)?",
        request=QueryRequest(query="irrelevant here", jurisdiction=Jurisdiction.IN),
    )

    intake.run(state, db_session)  # must not raise ValueError on the `requests` insert

    row = db_session.execute(
        sa.select(intake.requests_table).where(
            intake.requests_table.c.id == uuid.UUID(request_id)
        )
    ).first()
    assert row is not None
    assert str(row.id) == request_id
