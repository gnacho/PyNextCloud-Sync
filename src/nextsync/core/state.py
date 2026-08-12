from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable

from nextsync.nextcloud.nextcloudcmd_progress import SyncProgress


class AppState(str, Enum):
    UNCONFIGURED = "unconfigured"
    IDLE_OK = "idle_ok"
    IDLE_MANUAL_ONLY = "idle_manual_only"
    SYNC_QUEUED = "sync_queued"
    SYNCING = "syncing"
    PAUSED_USER = "paused_user"
    PAUSED_BATTERY = "paused_battery"
    OFFLINE = "offline"
    ERROR = "error"
    AUTH_REQUIRED = "auth_required"
    KEYRING_LOCKED = "keyring_locked"
    DELETE_REVIEW = "delete_review"


class PushState(str, Enum):
    DISABLED = "disabled"
    UNSUPPORTED = "unsupported"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    AUTH_REQUIRED = "authentication_required"


@dataclass(frozen=True)
class StateSnapshot:
    state: AppState
    message: str = ""


class StateController:
    def __init__(self, initial: AppState = AppState.UNCONFIGURED) -> None:
        self._snapshot = StateSnapshot(initial)
        self._listeners: list[Callable[[StateSnapshot], None]] = []
        self._progress: SyncProgress | None = None
        self._progress_listeners: list[Callable[[SyncProgress | None], None]] = []

    @property
    def snapshot(self) -> StateSnapshot:
        return self._snapshot

    @property
    def progress(self) -> SyncProgress | None:
        return self._progress

    def subscribe(self, callback: Callable[[StateSnapshot], None]) -> Callable[[], None]:
        self._listeners.append(callback)
        callback(self._snapshot)

        def unsubscribe() -> None:
            if callback in self._listeners:
                self._listeners.remove(callback)

        return unsubscribe

    def set(self, state: AppState, message: str = "") -> None:
        updated = StateSnapshot(state, message)
        if updated == self._snapshot:
            return
        self._snapshot = updated
        for listener in tuple(self._listeners):
            listener(updated)

    def set_progress(self, progress: SyncProgress | None) -> None:
        if progress == self._progress:
            return
        self._progress = progress
        for listener in tuple(self._progress_listeners):
            listener(progress)

    def subscribe_progress(
        self, callback: Callable[[SyncProgress | None], None]
    ) -> Callable[[], None]:
        self._progress_listeners.append(callback)
        callback(self._progress)

        def unsubscribe() -> None:
            if callback in self._progress_listeners:
                self._progress_listeners.remove(callback)

        return unsubscribe


_STATE_SEVERITY: dict[AppState, int] = {
    AppState.DELETE_REVIEW: 100,
    AppState.ERROR: 90,
    AppState.AUTH_REQUIRED: 80,
    AppState.KEYRING_LOCKED: 70,
    AppState.OFFLINE: 60,
    AppState.SYNCING: 50,
    AppState.SYNC_QUEUED: 40,
    AppState.PAUSED_BATTERY: 30,
    AppState.PAUSED_USER: 20,
    AppState.IDLE_MANUAL_ONLY: 10,
    AppState.IDLE_OK: 0,
    AppState.UNCONFIGURED: -10,
}


class AggregateStateController:
    """Expose the worst state across several account controllers."""

    def __init__(self, controllers: list[StateController] | None = None) -> None:
        self._controllers: list[StateController] = []
        self._unsubscribes: list[Callable[[], None]] = []
        self._listeners: list[Callable[[StateSnapshot], None]] = []
        self._progress_listeners: list[Callable[[SyncProgress | None], None]] = []
        self._snapshot = StateSnapshot(AppState.UNCONFIGURED)
        for controller in controllers or []:
            self.add(controller)

    @property
    def snapshot(self) -> StateSnapshot:
        return self._snapshot

    @property
    def progress(self) -> SyncProgress | None:
        current = next(
            (controller for controller in self._controllers if controller.progress),
            None,
        )
        return current.progress if current else None

    def subscribe_progress(
        self, callback: Callable[[SyncProgress | None], None]
    ) -> Callable[[], None]:
        self._progress_listeners.append(callback)
        callback(self.progress)

        def unsubscribe() -> None:
            if callback in self._progress_listeners:
                self._progress_listeners.remove(callback)

        return unsubscribe

    def add(self, controller: StateController) -> None:
        self._controllers.append(controller)
        self._unsubscribes.append(controller.subscribe(self._recompute))
        self._unsubscribes.append(
            controller.subscribe_progress(self._recompute_progress)
        )
        self._recompute()
        self._recompute_progress()

    def remove(self, controller: StateController) -> None:
        for index, current in enumerate(self._controllers):
            if current is controller:
                self._controllers.pop(index)
                unsubscribe = self._unsubscribes.pop(index * 2)
                unsubscribe()
                unsubscribe = self._unsubscribes.pop(index * 2)
                unsubscribe()
                self._recompute()
                self._recompute_progress()
                return

    def clear(self) -> None:
        for unsubscribe in self._unsubscribes:
            unsubscribe()
        self._unsubscribes.clear()
        self._controllers.clear()
        self._recompute()
        self._recompute_progress()

    def subscribe(self, callback: Callable[[StateSnapshot], None]) -> Callable[[], None]:
        self._listeners.append(callback)
        callback(self._snapshot)

        def unsubscribe() -> None:
            if callback in self._listeners:
                self._listeners.remove(callback)

        return unsubscribe

    def _recompute_progress(self, _progress: SyncProgress | None = None) -> None:
        progress = self.progress
        for listener in tuple(self._progress_listeners):
            listener(progress)

    def _recompute(self, _snapshot: StateSnapshot | None = None) -> None:
        if not self._controllers:
            updated = StateSnapshot(AppState.UNCONFIGURED)
            if updated == self._snapshot:
                return
            self._snapshot = updated
            for listener in tuple(self._listeners):
                listener(updated)
            return
        worst = self._controllers[0].snapshot.state
        worst_message = self._controllers[0].snapshot.message
        for controller in self._controllers[1:]:
            snapshot = controller.snapshot
            if _STATE_SEVERITY.get(snapshot.state, 0) > _STATE_SEVERITY.get(worst, 0):
                worst = snapshot.state
                worst_message = snapshot.message
        updated = StateSnapshot(worst, worst_message)
        if updated == self._snapshot:
            return
        self._snapshot = updated
        for listener in tuple(self._listeners):
            listener(updated)
