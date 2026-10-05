"""§6.4 `route`: thin wrapper around `orchestrator/router.py`."""

from __future__ import annotations

from app.orchestrator import router
from app.orchestrator.state import RequestState


def run(state: RequestState) -> None:
    state.intent, state.direct_section_key = router.route(state.query_en)
    if state.intent == "out_of_scope" and state.conversation_context and not router._UNRELATED.search(state.query_en):
        state.intent, state.direct_section_key = router.route(
            state.query_en + "\nPrior topic: " + state.conversation_context
        )
