"""`make eval` runner for the current live corpus version."""

from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.core.db import SessionLocal  # noqa: E402
from app.eval_runner import evaluate_live_version  # noqa: E402


def run() -> dict:
    with SessionLocal() as session:
        return evaluate_live_version(session)


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
