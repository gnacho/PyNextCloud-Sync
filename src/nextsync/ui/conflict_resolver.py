from __future__ import annotations

from collections import deque
from threading import Lock

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk, Pango

from nextsync.core.conflict_files import (
    ConflictFile,
    describe_modified,
    find_conflicts,
    keep_local,
    keep_remote,
)
from nextsync.ui.activity import ActivityEntry, LEVEL_ICONS, parse_activity_line
from nextsync.util.i18n import _


class ConflictResolverWindow(Adw.Window):
    """Unified recent-activity and conflicted-copy view.

    The Conflicts tab lists the files nextcloudcmd preserves as
    ``* (Nextcloud conflicted copy <date>).*`` and lets the user resolve each one
    manually (keep local, keep remote, or open in Files). The Recent tab shows
    the live synchronization log so an entry such as "Synchronized with
    conflicts" has context. The window never runs nextcloudcmd; it only scans
    the synchronized folder and performs local file operations.
    """

    def __init__(
        self,
        application: Gtk.Application,
        local_root: str,
        logger: object,
        on_close: object | None = None,
    ) -> None:
        super().__init__(application=application, title=_("Sync Activity and Conflicts"))
        self.set_default_size(820, 600)
        self.local_root = local_root
        self.logger = logger
        self.on_close = on_close
        self._log_lines: deque[str] = deque(maxlen=200)
        self._log_lock = Lock()
        self._log_idle_source = 0
        self._disposed = False

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        toolbar.add_top_bar(header)

        switcher = Adw.ViewSwitcher()
        switcher.set_policy(Adw.ViewSwitcherPolicy.WIDE)
        header.set_title_widget(switcher)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)

        self.stack = Adw.ViewStack()
        self._build_recent_page()
        self._build_conflicts_page()
        switcher.set_stack(self.stack)
        content.append(self.stack)

        refresh = Gtk.Button(label=_("Refresh"), icon_name="view-refresh-symbolic")
        refresh.connect("clicked", lambda _button: self._reload_conflicts())
        header.pack_end(refresh)
        close = Gtk.Button(label=_("Close"), css_classes=["suggested-action"])
        close.connect("clicked", lambda _button: self.close())
        header.pack_end(close)

        toolbar.set_content(content)
        self.set_content(toolbar)
        self.connect("close-request", self._close_request)
        self._log_unsubscribe = self.logger.subscribe(self._log_line)
        self._load_recent()
        self._reload_conflicts()

    def _build_recent_page(self) -> None:
        page = Adw.ViewStackPage()
        page.set_name("recent")
        page.set_title(_("Recent"))
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(4)
        box.set_margin_bottom(4)
        self.recent_list = Gtk.ListBox(css_classes=["boxed-list"], selection_mode=Gtk.SelectionMode.NONE)
        scroller = Gtk.ScrolledWindow(vexpand=True)
        scroller.set_child(self.recent_list)
        box.append(scroller)
        page.set_child(box)
        self.stack.add_named(page, "recent")

    def _build_conflicts_page(self) -> None:
        page = Adw.ViewStackPage()
        page.set_name("conflicts")
        page.set_title(_("Conflicts"))
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(4)
        box.set_margin_bottom(4)
        self.summary = Gtk.Label(xalign=0, css_classes=["dim-label"], wrap=True)
        box.append(self.summary)
        self.empty_state = Adw.StatusPage(
            icon_name="emblem-ok-symbolic",
            title=_("No Conflicts"),
            description=_("No Nextcloud conflicted copies were found in this folder."),
            vexpand=True,
        )
        self.empty_state.set_visible(False)
        box.append(self.empty_state)
        self.conflict_list = Gtk.ListBox(css_classes=["boxed-list"], selection_mode=Gtk.SelectionMode.NONE)
        scroller = Gtk.ScrolledWindow(vexpand=True)
        scroller.set_child(self.conflict_list)
        box.append(scroller)
        page.set_child(box)
        self.stack.add_named(page, "conflicts")

    def _close_request(self, _window: Gtk.Window) -> bool:
        self._dispose()
        if self.on_close:
            self.on_close(self)
        return False

    def _dispose(self) -> None:
        if self._disposed:
            return
        self._disposed = True
        if self._log_idle_source:
            GLib.source_remove(self._log_idle_source)
            self._log_idle_source = 0
        if self._log_unsubscribe:
            self._log_unsubscribe()
            self._log_unsubscribe = None
        with self._log_lock:
            self._log_lines.clear()

    def _log_line(self, line: str) -> None:
        with self._log_lock:
            self._log_lines.append(line)
            if self._log_idle_source:
                return
            self._log_idle_source = GLib.idle_add(self._drain_recent)
        if len(self._log_lines) > 200:
            with self._log_lock:
                self._log_lines.clear()

    def _drain_recent(self) -> bool:
        self._log_idle_source = 0
        if self._disposed:
            return GLib.SOURCE_REMOVE
        while row := self.recent_list.get_first_child():
            self.recent_list.remove(row)
        with self._log_lock:
            lines = tuple(self._log_lines)
        entries = [parse_activity_line(line) for line in lines]
        for entry in entries[-50:]:
            self.recent_list.append(self._recent_row(entry))
        return GLib.SOURCE_REMOVE

    def _load_recent(self) -> None:
        with self._log_lock:
            self._log_lines = deque(
                (self.logger.recent_lines(200)),
                maxlen=200,
            )
        self._drain_recent()

    def _recent_row(self, entry: ActivityEntry) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow(activatable=False, selectable=False)
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box.set_margin_top(7)
        box.set_margin_bottom(7)
        box.set_margin_start(12)
        box.set_margin_end(12)
        icon = Gtk.Image(icon_name=entry.icon_name, pixel_size=16)
        box.append(icon)
        label = Gtk.Label(label=entry.message, xalign=0, hexpand=True, wrap=True)
        label.set_ellipsize(Pango.EllipsizeMode.END)
        label.set_lines(2)
        box.append(label)
        row.set_child(box)
        return row

    def _reload_conflicts(self) -> None:
        while row := self.conflict_list.get_first_child():
            self.conflict_list.remove(row)
        conflicts = find_conflicts(self.local_root)
        if not conflicts:
            self.empty_state.set_visible(True)
            self.summary.set_text(_("No conflicted copies found in {folder}.").format(folder=self.local_root))
            return
        self.empty_state.set_visible(False)
        self.summary.set_text(
            _("{count} conflicted copy(ies) found in {folder}.").format(
                count=len(conflicts), folder=self.local_root
            )
        )
        for conflict in conflicts:
            self.conflict_list.append(self._build_row(conflict))

    def _build_row(self, conflict: ConflictFile) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(12)
        box.set_margin_end(12)

        icon = Gtk.Image(icon_name="dialog-warning-symbolic", pixel_size=24)
        box.append(icon)

        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True)
        title = Gtk.Label(
            label=conflict.name,
            xalign=0,
            wrap=False,
            ellipsize=True,
        )
        subtitle = Gtk.Label(
            label=_("Original: {original} · {date} · {size} bytes").format(
                original=conflict.original_name,
                date=describe_modified(conflict.modified),
                size=conflict.size,
            ),
            xalign=0,
            css_classes=["dim-label"],
            wrap=True,
        )
        text.append(title)
        text.append(subtitle)
        box.append(text)

        keep_local_button = Gtk.Button(label=_("Keep Local"))
        keep_local_button.set_tooltip_text(_("Delete the conflicted copy, keep the working file."))
        keep_local_button.connect("clicked", self._keep_local, conflict)
        box.append(keep_local_button)

        keep_remote_button = Gtk.Button(label=_("Keep Remote"), css_classes=["suggested-action"])
        keep_remote_button.set_tooltip_text(_("Replace the working file with the conflicted copy."))
        keep_remote_button.connect("clicked", self._keep_remote, conflict)
        box.append(keep_remote_button)

        open_button = Gtk.Button(icon_name="folder-symbolic")
        open_button.set_tooltip_text(_("Open in Files"))
        open_button.connect("clicked", self._open, conflict)
        box.append(open_button)

        row.set_child(box)
        return row

    def _keep_local(self, _button: Gtk.Button, conflict: ConflictFile) -> None:
        if keep_local(conflict):
            self._toast(_("Kept local version of {name}").format(name=conflict.original_name))
            self._reload_conflicts()

    def _keep_remote(self, _button: Gtk.Button, conflict: ConflictFile) -> None:
        if keep_remote(conflict):
            self._toast(_("Kept remote version of {name}").format(name=conflict.original_name))
            self._reload_conflicts()

    def _open(self, _button: Gtk.Button, conflict: ConflictFile) -> None:
        Gio.AppInfo.launch_default_for_uri(conflict.path.as_uri(), None)

    def _toast(self, message: str) -> None:
        overlay = self.get_ancestor(Adw.ToastOverlay)
        if overlay:
            overlay.add_toast(Adw.Toast(title=message))
