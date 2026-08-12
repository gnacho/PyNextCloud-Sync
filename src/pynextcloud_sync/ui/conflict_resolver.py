from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, Gtk

from pynextcloud_sync.core.conflict_files import (
    ConflictFile,
    describe_modified,
    find_conflicts,
    keep_local,
    keep_remote,
)
from pynextcloud_sync.util.i18n import _


class ConflictResolverWindow(Adw.Window):
    """List conflicted copies produced by nextcloudcmd and let the user triage.

    This window never runs nextcloudcmd. It only scans the synchronized folder
    for files matching the engine's conflicted-copy naming pattern and performs
    local file operations. The engine keeps writing conflict copies whether or
    not this view is open.
    """

    def __init__(
        self,
        application: Gtk.Application,
        local_root: str,
        on_close: object | None = None,
    ) -> None:
        super().__init__(application=application, title=_("Resolve Conflicts"))
        self.set_default_size(760, 560)
        self.local_root = local_root
        self.on_close = on_close

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        toolbar.add_top_bar(header)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content.set_margin_top(16)
        content.set_margin_bottom(16)
        content.set_margin_start(18)
        content.set_margin_end(18)

        self.summary = Gtk.Label(xalign=0, css_classes=["dim-label"], wrap=True)
        content.append(self.summary)

        self.empty_state = Adw.StatusPage(
            icon_name="emblem-ok-symbolic",
            title=_("No Conflicts"),
            description=_("No Nextcloud conflicted copies were found in this folder."),
            vexpand=True,
        )
        self.empty_state.set_visible(False)
        content.append(self.empty_state)

        self.listbox = Gtk.ListBox(css_classes=["boxed-list"], selection_mode=Gtk.SelectionMode.NONE)
        scroller = Gtk.ScrolledWindow(vexpand=True)
        scroller.set_child(self.listbox)
        content.append(scroller)

        refresh = Gtk.Button(label=_("Refresh"), icon_name="view-refresh-symbolic")
        refresh.connect("clicked", lambda _button: self._reload())
        header.pack_end(refresh)
        close = Gtk.Button(label=_("Close"), css_classes=["suggested-action"])
        close.connect("clicked", lambda _button: self.close())
        header.pack_end(close)

        toolbar.set_content(content)
        self.set_content(toolbar)
        self.connect("close-request", self._close_request)
        self._reload()

    def _close_request(self, _window: Gtk.Window) -> bool:
        if self.on_close:
            self.on_close(self)
        return False

    def _reload(self) -> None:
        while row := self.listbox.get_first_child():
            self.listbox.remove(row)
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
            self.listbox.append(self._build_row(conflict))

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
            self._reload()

    def _keep_remote(self, _button: Gtk.Button, conflict: ConflictFile) -> None:
        if keep_remote(conflict):
            self._toast(_("Kept remote version of {name}").format(name=conflict.original_name))
            self._reload()

    def _open(self, _button: Gtk.Button, conflict: ConflictFile) -> None:
        Gio.AppInfo.launch_default_for_uri(conflict.path.as_uri(), None)

    def _toast(self, message: str) -> None:
        overlay = self.get_ancestor(Adw.ToastOverlay)
        if overlay:
            overlay.add_toast(Adw.Toast(title=message))
