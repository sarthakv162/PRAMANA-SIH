"""§6.4 `cache`: key = `(query_hash, corpus_version, as_of, jurisdictions, lang)`. A hit
skips straight to `render` — reusing the retrieved evidence and verified claims, not the
rendered card itself, since a fresh `request_id`/receipt is still minted per request (the
audit chain is append-only per request, cache hit or not).

In-memory, per-process — real enough to demonstrate the "hit → skip retrieve/generate/verify"
behaviour and to speed up repeated demo queries, but it doesn't survive a restart or scale
across workers. A persistent cache (Redis, or a DB table) is a reasonable upgrade, not a
correctness requirement for the prototype.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.orchestrator.state import RequestState

if TYPE_CHECKING:
    from app.retrieval.evidence_pack import NumberedSpan
    from app.schemas.claims import Claim


@dataclass
class CachedAnswer:
    evidence_pack: list[NumberedSpan]
    verified_claims: list[Claim]
    dropped_claims: int
    mean_entailment: float
    retrieval_margin: float
    gaps: list[str]
    needs_clarification: str | None


_CACHE: dict[tuple[str, str, str, tuple[str, ...], str], CachedAnswer] = {}
MAX_ENTRIES = 500


def _key(state: RequestState) -> tuple[str, str, str, tuple[str, ...], str]:
    return (
        state.query_hash,
        state.corpus_version_id,
        state.as_of.isoformat(),
        tuple(state.jurisdictions),
        state.lang.value,
    )


def get(state: RequestState) -> CachedAnswer | None:
    return _CACHE.get(_key(state))


def put(state: RequestState, answer: CachedAnswer) -> None:
    if len(_CACHE) >= MAX_ENTRIES:
        _CACHE.pop(next(iter(_CACHE)))  # evict oldest-inserted, dict preserves insertion order
    _CACHE[_key(state)] = answer


def clear() -> None:
    """Test-only — cache state must not leak between test cases."""
    _CACHE.clear()
