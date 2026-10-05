"""Resolve explicitly named instruments against the selected corpus's actual sources."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import yaml


def _words(text: str) -> str:
    return " ".join(re.findall(r"\w+", text.casefold()))


@lru_cache
def _instruments() -> tuple[tuple[str, tuple[str, ...]], ...]:
    path = Path(__file__).resolve().parents[3] / "corpus/coverage.yaml"
    catalog = yaml.safe_load(path.read_text())
    return tuple(
        (_words(alias), tuple(instrument["sources"]))
        for instrument in catalog["instruments"]
        for alias in instrument["aliases"]
    )


def requested_sources(query: str) -> set[str]:
    """Only explicit instrument names restrict search; general subject questions do not."""
    normalized = " " + _words(query) + " "
    return {source for alias, sources in _instruments() if " " + alias + " " in normalized for source in sources}
