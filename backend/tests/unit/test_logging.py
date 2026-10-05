from __future__ import annotations

import logging

import pytest

from app.core.logging import configure_logging


def test_http_transport_logs_do_not_emit_signed_request_urls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = logging.getLogger()
    monkeypatch.setattr(root, "handlers", root.handlers.copy())
    monkeypatch.setattr(root, "level", root.level)
    for name in ("httpx", "httpcore"):
        logger = logging.getLogger(name)
        monkeypatch.setattr(logger, "level", logging.NOTSET)
    configure_logging()
    assert logging.getLogger("httpx").level == logging.WARNING
    assert logging.getLogger("httpcore").level == logging.WARNING
