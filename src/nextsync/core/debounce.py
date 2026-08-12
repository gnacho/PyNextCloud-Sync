from __future__ import annotations

from typing import Callable


class DebounceGate:
    """Serialize local feedback into a single delayed start.

    Local filesystem events arrive in bursts. This gate collapses them into
    one ``on_ready`` call after a quiet window and then holds a cooldown so the
    next reconciliation does not start immediately after the previous one.
    """

    def __init__(
        self,
        *,
        debounce_ms: int,
        cooldown_seconds: int,
        on_ready: Callable[[], None],
        glib: object | None = None,
    ) -> None:
        if glib is None:
            from gi.repository import GLib

            glib = GLib
        self._glib = glib
        self.debounce_ms = debounce_ms
        self.cooldown_seconds = cooldown_seconds
        self.on_ready = on_ready
        self.debounce_source = 0
        self.cooldown_source = 0
        self._cooldown_callback: Callable[[], None] | None = None

    @property
    def in_cooldown(self) -> bool:
        return self.cooldown_source != 0

    def kick(self) -> None:
        if self.debounce_source:
            self._glib.source_remove(self.debounce_source)
        self.debounce_source = self._glib.timeout_add(
            self.debounce_ms, self._debounce_elapsed
        )

    def _debounce_elapsed(self) -> bool:
        self.debounce_source = 0
        self.on_ready()
        return self._glib.SOURCE_REMOVE

    def begin_cooldown(self, on_finished: Callable[[], None] | None = None) -> None:
        self._cooldown_callback = on_finished
        self.cooldown_source = self._glib.timeout_add_seconds(
            self.cooldown_seconds, self._cooldown_finished
        )

    def _cooldown_finished(self) -> bool:
        self.cooldown_source = 0
        callback = self._cooldown_callback
        self._cooldown_callback = None
        if callback:
            callback()
        return self._glib.SOURCE_REMOVE

    def stop(self) -> None:
        for attribute in ("debounce_source", "cooldown_source"):
            source = getattr(self, attribute)
            if source:
                self._glib.source_remove(source)
                setattr(self, attribute, 0)
        self._cooldown_callback = None
