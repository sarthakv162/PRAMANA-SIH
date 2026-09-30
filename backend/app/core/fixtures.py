"""MOCK_MODE fixture loading. Endpoints in MOCK_MODE=1 return these verbatim (§3, §6.13).

Fixture filenames are the frozen contract between this loader and contracts/fixtures/*.json
(see docs/IMPLEMENTATION_PLAN.md §5.6). Adding a new mock response = adding a fixture file here.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import get_settings


def _fixtures_root() -> Path:
    settings = get_settings()
    root = Path(settings.fixtures_dir)
    if not root.is_absolute():
        root = Path(__file__).resolve().parents[2] / root
    return root.resolve()


@lru_cache
def load_fixture(name: str) -> dict[str, Any]:
    path = _fixtures_root() / name
    result: dict[str, Any] = json.loads(path.read_text())
    return result


def load_fixture_text(name: str) -> str:
    path = _fixtures_root() / name
    return path.read_text()
