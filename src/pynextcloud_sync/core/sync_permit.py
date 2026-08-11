from __future__ import annotations

from typing import Callable


class SyncPermit:
    """Global gate limiting how many reconciliations run at once.

    The whole application runs on a single GLib main loop, so a plain boolean
    is enough: a scheduler acquires the permit just before launching
    ``nextcloudcmd`` and releases it when the run finishes. Schedulers that
    cannot acquire it register a release callback and retry later, so several
    accounts queue up instead of hammering the network at the same time.
    """

    def __init__(self, max_concurrent: int = 1) -> None:
        if max_concurrent < 1:
            raise ValueError("max_concurrent must be at least 1")
        self.max_concurrent = max_concurrent
        self._in_use = 0
        self._waiters: list[Callable[[], None]] = []

    @property
    def available(self) -> bool:
        return self._in_use < self.max_concurrent

    def try_acquire(self) -> bool:
        if not self.available:
            return False
        self._in_use += 1
        return True

    def release(self) -> None:
        if self._in_use > 0:
            self._in_use -= 1
        if self._waiters:
            self._waiters.pop(0)()

    def wait_for_release(self, callback: Callable[[], None]) -> None:
        self._waiters.append(callback)
