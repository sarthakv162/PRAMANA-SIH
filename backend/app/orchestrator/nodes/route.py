"""§6.4 `route`: thin wrapper around `orchestrator/router.py`."""

from __future__ import annotations

from app.orchestrator import router
from app.orchestrator.state import RequestState


def run(state: RequestState) -> None:
    state.intent, state.direct_section_key = router.route(state.query_en)
