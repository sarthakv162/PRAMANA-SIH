"""§6.4 `frame`: normalise `as_of` (default today) and expand `jurisdiction` (`BOTH` →
`[IN, INTL]`). Pure, no I/O — the query's own free-text date grammar ("as on 1 March 2023")
isn't handled here because `QueryRequest.as_of` is already a structured date; that parsing
would belong in the client/UI layer that produces it, not here.
"""

from __future__ import annotations

from datetime import date

from app.orchestrator.state import RequestState
from app.schemas.enums import Jurisdiction


def run(state: RequestState) -> None:
    state.as_of = state.request.as_of or date.today()
    if state.request.jurisdiction == Jurisdiction.BOTH:
        state.jurisdictions = ["IN", "INTL"]
    else:
        state.jurisdictions = [state.request.jurisdiction.value]
