"""§6.10 ontology: normalise ingredient names (common/regional) to canonical Latin binomials.
Seed dataset — ~20 common Ayurvedic plants (`data/plants.csv`), not the ~200-plant target
(§6.10); state the size honestly rather than pad it out under time pressure.

Exact match, then trigram fallback (`difflib`, no extra dependency) — genuinely ambiguous
names return multiple candidates with confidence rather than silently picking one (§6.10).
"""

from __future__ import annotations

import csv
import difflib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

DATA_PATH = Path(__file__).parent / "data" / "plants.csv"


@dataclass
class PlantEntry:
    latin: str
    sanskrit: str
    regional: dict[str, str]  # lang -> name
    synonyms: list[str]


@lru_cache
def _load_plants() -> list[PlantEntry]:
    entries = []
    with DATA_PATH.open() as f:
        for row in csv.DictReader(f):
            entries.append(
                PlantEntry(
                    latin=row["latin"],
                    sanskrit=row["sanskrit"],
                    regional={"hi": row["hi"], "ta": row["ta"], "bn": row["bn"]},
                    synonyms=[s.strip() for s in row["synonyms"].split(";") if s.strip()],
                )
            )
    return entries


def _all_names(entry: PlantEntry) -> list[str]:
    return [entry.latin, entry.sanskrit, *entry.regional.values(), *entry.synonyms]


@dataclass
class NormalizeMatch:
    entry: PlantEntry
    confidence: float


def normalize_ingredient(name: str) -> list[NormalizeMatch]:
    """Returns candidates, best first. Confidence 1.0 = exact (case-insensitive) match."""
    needle = name.strip().lower()
    plants = _load_plants()

    exact = [p for p in plants if needle in {n.lower() for n in _all_names(p)}]
    if exact:
        return [NormalizeMatch(entry=p, confidence=1.0) for p in exact]

    scored: list[NormalizeMatch] = []
    for plant in plants:
        best = max(
            difflib.SequenceMatcher(None, needle, n.lower()).ratio() for n in _all_names(plant)
        )
        if best >= 0.6:
            scored.append(NormalizeMatch(entry=plant, confidence=round(best, 2)))
    return sorted(scored, key=lambda m: m.confidence, reverse=True)[:3]
