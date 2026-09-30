"""Shrinking-only request deadline (§6.4 intake, invariant I8).

`intake` creates a Deadline with `remaining() == REQUEST_DEADLINE_S`. Every later stage receives
the same Deadline instance via orchestrator state; a stage may call `shrink()` to lower the
budget for stages after it, but nothing may raise it back. `remaining()` going <= 0 means the
stage must stop and the orchestrator renders a `RefusalCard(reason=deadline_exceeded)`.
"""

from __future__ import annotations

import time


class DeadlineExceeded(Exception):
    pass


class Deadline:
    def __init__(self, budget_s: float) -> None:
        self._deadline_at = time.monotonic() + budget_s

    def remaining(self) -> float:
        return self._deadline_at - time.monotonic()

    def expired(self) -> bool:
        return self.remaining() <= 0

    def shrink(self, new_budget_s: float) -> None:
        """Lower the deadline to at most `new_budget_s` from now. Never raises it."""
        candidate = time.monotonic() + new_budget_s
        if candidate < self._deadline_at:
            self._deadline_at = candidate

    def check(self) -> None:
        if self.expired():
            raise DeadlineExceeded
