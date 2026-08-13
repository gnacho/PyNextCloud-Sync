from __future__ import annotations

from pathlib import Path
from typing import Callable, Mapping

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from nextsync.core.account import FolderSession
from nextsync.core.state import AppState, StateController, StateSnapshot
from nextsync.util.i18n import _


STATE_PRESENTATION: dict[AppState, tuple[str, str]] = {
    AppState.UNCONFIGURED: ("dialog-question-symbolic", _("Not Configured")),
    AppState.IDLE_OK: ("emblem-ok-symbolic", _("Synchronized")),
    AppState.IDLE_MANUAL_ONLY: ("media-playback-pause-symbolic", _("Automatic Sync Is Off")),
    AppState.SYNC_QUEUED: ("appointment-soon-symbolic", _("Synchronization Scheduled")),
    AppState.SYNCING: ("emblem-synchronizing-symbolic", _("Synchronizing…")),
    AppState.PAUSED_USER: ("media-playback-pause-symbolic", _("Paused")),
    AppState.PAUSED_BATTERY: ("battery-symbolic", _("Paused on Battery")),
    AppState.OFFLINE: ("network-offline-symbolic", _("Offline")),
    AppState.ERROR: ("dialog-error-symbolic", _("Synchronization Error")),
    AppState.AUTH_REQUIRED: ("dialog-password-symbolic", _("Account Needs Attention")),
    AppState.KEYRING_LOCKED: ("changes-prevent-symbolic", _("Password Keyring Locked")),
    AppState.DELETE_REVIEW: ("security-high-symbolic", _("Review Deletions")),
}


def folder_status_presentation(state: AppState) -> tuple[str, str]:
    """Return the ``(icon_name, status_label)`` pair for a folder's state."""
    return STATE_PRESENTATION[state]


def pair_folder_runtimes(
    folders: list[FolderSession], runtimes: Mapping[str, object]
) -> list[tuple[FolderSession, object | None]]:
    """Match folder sessions to folder runtimes by ``folder_id`` in session order.

    Runtimes are the ``AccountRuntime.folders`` mapping; a folder without a
    runtime (it should always have one) yields ``None`` and the row degrades to
    a static presentation.
    """
    return [(folder, runtimes.get(folder.folder_id)) for folder in folders]


class FolderStatusRow(Adw.ActionRow):
    """One synchronized folder rendered with its own live sync status."""

    def __init__(
        self,
        folder: FolderSession,
        state_controller: StateController | None,
        *,
        on_open: Callable[[], None],
        format_last_sync: Callable[[], str],
    ) -> None:
        super().__init__(activatable=True, selectable=False)
        self._folder = folder
        self._on_open = on_open
        self._format_last_sync = format_last_sync
        self._disposed = False
        self._unsubscribe: Callable[[], None] | None = None

        name = Path(folder.local_root).name or folder.local_root
        self.set_title(name)
        if hasattr(self, "set_title_lines"):
            self.set_title_lines(1)
        if hasattr(self, "set_subtitle_lines"):
            self.set_subtitle_lines(1)

        self._icon = Gtk.Image(icon_name="folder-symbolic", pixel_size=16)
        self.add_prefix(self._icon)

        self._spinner = Gtk.Spinner()
        self._spinner.set_visible(False)
        self.add_suffix(self._spinner)

        open_button = Gtk.Button(icon_name="folder-open-symbolic")
        open_button.set_valign(Gtk.Align.CENTER)
        open_button.connect("clicked", lambda _button: on_open())
        self.add_suffix(open_button)

        self.connect("activated", lambda _row: on_open())

        if state_controller is not None:
            self._unsubscribe = state_controller.subscribe(self._state_changed)
        else:
            self._render(StateSnapshot(AppState.UNCONFIGURED))

    def _state_changed(self, snapshot: StateSnapshot) -> None:
        if self._disposed:
            return
        self._render(snapshot)

    def _render(self, snapshot: StateSnapshot) -> None:
        icon, status = folder_status_presentation(snapshot.state)
        self._icon.set_from_icon_name(icon)
        syncing = snapshot.state == AppState.SYNCING
        self._spinner.set_visible(syncing)
        if syncing:
            self._spinner.start()
        else:
            self._spinner.stop()
        parts = [status]
        if self._folder.remote_path:
            parts.append(_("Remote: {path}").format(path=self._folder.remote_path))
        last_sync = self._format_last_sync()
        if last_sync:
            parts.append(last_sync)
        self.set_subtitle(" · ".join(parts))
        message = _(snapshot.message) if snapshot.message else None
        self.set_tooltip_text(message)

    def dispose(self) -> None:
        if self._disposed:
            return
        self._disposed = True
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None
        if hasattr(self, "_spinner"):
            self._spinner.stop()
