from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.ingest.cli import _resume_staged_version


class Result:
    def __init__(self, row: object | None) -> None:
        self._row = row

    def first(self) -> object | None:
        return self._row


class Session:
    def __init__(self, row: object | None) -> None:
        self.row = row

    def execute(self, _statement: object) -> Result:
        return Result(self.row)


def test_resume_accepts_only_an_existing_staged_version() -> None:
    version = SimpleNamespace(id="staged-id", status="staged")
    assert _resume_staged_version(Session(version), "staged-label") == "staged-id"


@pytest.mark.parametrize(
    ("row", "message"),
    [
        (None, "no corpus_version with label 'missing'"),
        (SimpleNamespace(id="live-id", status="live"), "not staged"),
    ],
)
def test_resume_rejects_missing_or_live_version(row: object | None, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        _resume_staged_version(Session(row), "missing")
