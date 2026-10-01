"""Small process-local per-IP request limiter for the prototype API."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


class RateLimiter:
    def __init__(self, requests: int, window_s: int) -> None:
        self.requests = max(1, requests)
        self.window_s = max(1, window_s)
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, identity: str, now: float | None = None) -> tuple[bool, int]:
        current = time.monotonic() if now is None else now
        cutoff = current - self.window_s
        with self._lock:
            hits = self._hits[identity]
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if len(hits) >= self.requests:
                return False, max(1, int(hits[0] + self.window_s - current + 0.999))
            hits.append(current)
            return True, 0

    def prune(self, now: float | None = None) -> None:
        """Drop inactive identities so the map remains bounded on long-lived processes."""
        current = time.monotonic() if now is None else now
        cutoff = current - self.window_s
        with self._lock:
            expired = [key for key, hits in self._hits.items() if not hits or hits[-1] <= cutoff]
            for key in expired:
                del self._hits[key]
