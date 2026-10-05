from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.main import app


@pytest.mark.parametrize(("mock_mode", "expected_calls"), [(True, 0), (False, 1)])
def test_lifespan_warms_models_only_for_live_mode(
    monkeypatch: pytest.MonkeyPatch, mock_mode: bool, expected_calls: int
) -> None:
    calls: list[str] = []
    monkeypatch.setattr("app.main.get_settings", lambda: SimpleNamespace(mock_mode=mock_mode))
    monkeypatch.setattr("app.main._warm_live_models", lambda: calls.append("warm"))

    async def exercise_lifespan() -> None:
        async with app.router.lifespan_context(app):
            assert len(calls) == expected_calls

    asyncio.run(exercise_lifespan())
