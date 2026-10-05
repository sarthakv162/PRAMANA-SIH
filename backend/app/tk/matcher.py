"""§6.10 matcher: weighted Jaccard over canonical ingredient sets against the seed classical
formulations (`data/classical_formulations.csv`, 10 entries — a seed, not the ~100 target;
state the size honestly).
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.tk.ontology import normalize_ingredient

DATA_PATH = Path(__file__).parent / "data" / "classical_formulations.csv"


@dataclass
class ClassicalFormulation:
    id: str
    name: str
    source_text: str
    ingredients: list[str]  # canonical Latin names
    indications: list[str]


@lru_cache
def _load_formulations() -> list[ClassicalFormulation]:
    entries = []
    with DATA_PATH.open() as f:
        for row in csv.DictReader(f):
            entries.append(
                ClassicalFormulation(
                    id=row["id"],
                    name=row["name"],
                    source_text=row["source_text"],
                    ingredients=[i.strip() for i in row["ingredients"].split(";") if i.strip()],
                    indications=[i.strip() for i in row["indications"].split(";") if i.strip()],
                )
            )
    return entries


@dataclass
class MatchResult:
    formulation: ClassicalFormulation
    similarity: float
    overlap: list[str]
    missing_in_input: list[str]
    extra_in_input: list[str]
    indication_match: bool


def canonicalize_ingredients(raw_names: list[str]) -> set[str]:
    canonical: set[str] = set()
    for name in raw_names:
        matches = normalize_ingredient(name)
        if matches:
            canonical.add(matches[0].entry.latin)
    return canonical


def match_formulations(ingredient_names: list[str], indication: str | None = None, top_n: int = 8) -> list[MatchResult]:
    input_set = canonicalize_ingredients(ingredient_names)
    results: list[MatchResult] = []

    for formulation in _load_formulations():
        formulation_set = set(formulation.ingredients)
        if not input_set and not formulation_set:
            continue
        intersection = input_set & formulation_set
        union = input_set | formulation_set
        similarity = len(intersection) / len(union) if union else 0.0
        indication_match = bool(indication and any(indication.lower() in i.lower() for i in formulation.indications))
        if indication_match:
            similarity = min(1.0, similarity + 0.15)  # indication overlap boost (§6.10)

        results.append(
            MatchResult(
                formulation=formulation,
                similarity=round(similarity, 2),
                overlap=sorted(intersection),
                missing_in_input=sorted(formulation_set - input_set),
                extra_in_input=sorted(input_set - formulation_set),
                indication_match=indication_match,
            )
        )

    return sorted(results, key=lambda r: r.similarity, reverse=True)[:top_n]
