"""Canonical hashing helpers used by the audit chain (§6.9) and PII log-scrubbing (§6.3, I4).

Never hash or log raw user text with anything other than these helpers — the audit chain and
the "no raw PII persisted" invariant (I4) both depend on hashes being computed the same way
everywhere.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def sha256_hex(data: str | bytes) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def canonical_json(obj: Any) -> str:
    """Deterministic JSON encoding: sorted keys, no extra whitespace.

    Two logically-identical payloads must hash identically regardless of key insertion order,
    since the audit chain (`entry_hash = sha256(prev_hash || canonical_json(entry))`) must be
    reproducible on replay/verify.
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def chain_entry_hash(prev_hash: str, entry: dict[str, Any]) -> str:
    return sha256_hex(prev_hash + canonical_json(entry))
