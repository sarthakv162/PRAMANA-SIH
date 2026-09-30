"""Shared pytest fixtures. Points the app at contracts/fixtures/ and forces MOCK_MODE=1
before anything imports app.config, so `get_settings()` (lru_cache'd) picks it up once.
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("MOCK_MODE", "1")
os.environ.setdefault(
    "FIXTURES_DIR", str(Path(__file__).resolve().parents[2] / "contracts" / "fixtures")
)
# Model weights (embed/NLI) are already cached locally by the time tests run; skip the
# hub-metadata HTTP round trips that otherwise slow every model load down by ~30s.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

import pytest
from fastapi.testclient import TestClient

from app.main import app

FIXTURES_DIR = Path(os.environ["FIXTURES_DIR"])


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
