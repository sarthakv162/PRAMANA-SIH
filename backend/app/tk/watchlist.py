"""§6.10 watchlist: match seeded biopiracy cases (`data/watchlist.yaml`) by ingredient."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.tk.ontology import normalize_ingredient

DATA_PATH = Path(__file__).parent / "data" / "watchlist.yaml"


@lru_cache
def _load_cases() -> list[dict[str, Any]]:
    data: dict[str, Any] = yaml.safe_load(DATA_PATH.read_text())
    cases: list[dict[str, Any]] = data["cases"]
    return cases


def matching_watchlist_hits(ingredient_names: list[str]) -> list[dict[str, Any]]:
    canonical_latins = set()
    for name in ingredient_names:
        matches = normalize_ingredient(name)
        if matches:
            canonical_latins.add(matches[0].entry.latin)

    hits = []
    for case in _load_cases():
        species = set(case.get("species", []))
        if canonical_latins & species:
            hits.append(case)
    return hits
