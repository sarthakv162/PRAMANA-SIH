"""Structured logging. Invariant I4: never persist raw user text — log only sha256 of the
PII-scrubbed query. Call sites must pass `query_hash`, never `query` itself.
"""

from __future__ import annotations

import logging
import sys


def configure_logging(level: int = logging.INFO) -> None:
    # httpx INFO records include the complete URL. WIPO Lex uses short-lived signed
    # download URLs, so forwarding transport logs would disclose their query signatures.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers = [handler]


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
