from __future__ import annotations

import datetime as dt
from collections import deque
from pathlib import Path
from threading import Lock
from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Pango

from nextsync import APP_NAME
from nextsync.core.account import AccountSession
from nextsync.core.state import AppState, StateSnapshot
from nextsync.nextcloud.nextcloudcmd_progress import SyncProgress
from nextsync.util.i18n import _

from .about import show_about_dialog
from .activity import ActivityEntry, parse_activity_line
from .log_view import LogWindow


STATE_PRESENTATION = {
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


def _compact_action_row(**properties: object) -> Adw.ActionRow:
    row = Adw.ActionRow(**properties)
    if hasattr(row, "set_title_lines"):
        row.set_title_lines(1)
    if hasattr(row, "set_subtitle_lines"):
        row.set_subtitle_lines(1)
    return row


class AccountView(Gtk.Box):
    """The synchronization panel for one account."""

    def __init__(
        self,
        application: Gtk.Application,
        config: object,
        session: AccountSession,
        runtime: object,
        logger: object,
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.application = application
        self.config = config
        self.session = session
        self.runtime = runtime
        self.logger = logger
        self.log_window: LogWindow | None = None
        self._recent_entries: list[ActivityEntry] = [
            parse_activity_line(line) for line in logger.recent_lines(5)
        ]
        self._activity_rows: list[Gtk.ListBoxRow] = []
        self._expanded_activity_entries: set[int] = set()
        self._pending_activity_lines: deque[str] = deque(maxlen=5)
        self._activity_lock = Lock()
        self._activity_idle_source = 0
        self._disposed = False

        self.set_margin_top(16)
        self.set_margin_bottom(16)
        self.set_margin_start(18)
        self.set_margin_end(18)

        status_list = Gtk.ListBox(css_classes=["boxed-list"], selection_mode=Gtk.SelectionMode.NONE)
        status_row = Gtk.ListBoxRow(activatable=False, selectable=False)
        status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        status_box.set_margin_top(14)
        status_box.set_margin_bottom(14)
        status_box.set_margin_start(16)
        status_box.set_margin_end(16)
        self.status_icon = Gtk.Image(icon_name="emblem-ok-symbolic", pixel_size=48)
        self.status_icon.set_valign(Gtk.Align.CENTER)
        status_box.append(self.status_icon)
        status_text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, valign=Gtk.Align.CENTER)
        self.status_title = Gtk.Label(xalign=0, css_classes=["title-3"])
        self.status_title.set_ellipsize(Pango.EllipsizeMode.END)
        self.status_title.set_single_line_mode(True)
        self.status_description = Gtk.Label(xalign=0, css_classes=["dim-label"])
        self.status_description.set_ellipsize(Pango.EllipsizeMode.END)
        self.status_description.set_single_line_mode(True)
        self.status_progress = Gtk.Label(xalign=0, css_classes=["dim-label"])
        self.status_progress.set_ellipsize(Pango.EllipsizeMode.END)
        self.status_progress.set_single_line_mode(True)
        self.status_progress.set_visible(False)
        status_text.append(self.status_title)
        status_text.append(self.status_description)
        status_text.append(self.status_progress)
        status_box.append(status_text)
        status_row.set_child(status_box)
        status_list.append(status_row)
        self.append(status_list)

        account = self.session.account_dict
        account_list = Gtk.ListBox(css_classes=["boxed-list"], selection_mode=Gtk.SelectionMode.NONE)
        account_list.append(
            _compact_action_row(
                title=account["login_name"],
                subtitle=account["server_url"],
                icon_name="avatar-default-symbolic",
            )
        )
        if self.session.folders:
            for folder in self.session.folders:
                folder_row = _compact_action_row(
                    title=_("Local Folder"),
                    subtitle=folder.local_root,
                    icon_name="folder-symbolic",
                    activatable=True,
                )
                folder_row.add_suffix(Gtk.Image.new_from_icon_name("go-next-symbolic"))
                folder_row.connect("activated", lambda _row, _folder=folder: self.open_folder(_folder))
                account_list.append(folder_row)
                if folder.remote_path:
                    account_list.append(
                        _compact_action_row(
                            title=_("Remote Folder"),
                            subtitle=folder.remote_path,
                            icon_name="folder-remote-symbolic",
                        )
                    )
        else:
            account_list.append(
                _compact_action_row(
                    title=_("No Synchronization Folders"),
                    subtitle=_("Add folders from Settings"),
                    icon_name="folder-symbolic",
                )
            )
        self.last_row = _compact_action_row(
            title=_("Last Successful Sync"),
            subtitle=self._format_last_sync(),
            icon_name="document-open-recent-symbolic",
        )
        account_list.append(self.last_row)
        self.append(account_list)

        self.buttons = Gtk.Box(spacing=12, homogeneous=True)
        self.sync_content = Adw.ButtonContent(
            label=_("Sync Now"), icon_name="emblem-synchronizing-symbolic"
        )
        self.sync_button = Gtk.Button(child=self.sync_content, css_classes=["suggested-action", "pill"])
        self.sync_button.connect("clicked", self._sync_clicked)
        self.buttons.append(self.sync_button)
        self.pause_content = Adw.ButtonContent(
            label=_("Pause Sync"), icon_name="media-playback-pause-symbolic"
        )
        self.pause_button = Gtk.Button(child=self.pause_content, css_classes=["pill"])
        self.pause_button.connect("clicked", self._pause_clicked)
        self.buttons.append(self.pause_button)
        self.append(self.buttons)

        self.activity_expander = Adw.ExpanderRow(
            title=_("Recent Activity"),
            subtitle=_("No activity in this session"),
            icon_name="document-open-recent-symbolic",
            expanded=False,
        )
        if hasattr(self.activity_expander, "set_title_lines"):
            self.activity_expander.set_title_lines(1)
        if hasattr(self.activity_expander, "set_subtitle_lines"):
            self.activity_expander.set_subtitle_lines(1)
        activity_list = Gtk.ListBox(css_classes=["boxed-list"], selection_mode=Gtk.SelectionMode.NONE)
        activity_list.append(self.activity_expander)
        self.append(activity_list)

        self.view_log_row = _compact_action_row(
            title=_("View Synchronization Log"),
            icon_name="text-x-generic-symbolic",
            activatable=True,
        )
        self.view_log_row.add_suffix(Gtk.Image.new_from_icon_name("go-next-symbolic"))
        self.view_log_row.connect("activated", lambda _row: self.show_log())
        self.conflicts_row = _compact_action_row(
            title=_("Resolve Conflicts"),
            icon_name="dialog-warning-symbolic",
            activatable=True,
        )
        self.conflicts_row.add_suffix(Gtk.Image.new_from_icon_name("go-next-symbolic"))
        self.conflicts_row.connect("activated", lambda _row: self._show_conflicts())
        self._refresh_activity()

        if hasattr(Adw, "Breakpoint") and hasattr(self, "add_breakpoint"):
            condition = Adw.BreakpointCondition.parse("max-width: 520px")
            breakpoint = Adw.Breakpoint.new(condition)
            breakpoint.add_setter(self.buttons, "orientation", Gtk.Orientation.VERTICAL)
            breakpoint.add_setter(self, "margin-start", 9)
            breakpoint.add_setter(self, "margin-end", 9)
            self.add_breakpoint(breakpoint)

        self._state_unsubscribe = self.runtime.state.subscribe(self._state_changed)
        self._progress_unsubscribe = self.runtime.state.subscribe_progress(
            self._progress_changed
        )
        self._log_unsubscribe = self.logger.subscribe(self._log_line)

    def _state_changed(self, snapshot: StateSnapshot) -> None:
        icon, title = STATE_PRESENTATION[snapshot.state]
        self.status_icon.set_from_icon_name(icon)
        self.status_title.set_text(title)
        description = _(snapshot.message) if snapshot.message else _("Your files are ready.")
        self.status_description.set_text(description)
        self.status_description.set_tooltip_text(description)
        self.status_progress.set_visible(snapshot.state == AppState.SYNCING)
        paused = snapshot.state == AppState.PAUSED_USER
        self.pause_content.set_label(_("Resume Sync") if paused else _("Pause Sync"))
        self.pause_content.set_icon_name(
            "media-playback-start-symbolic" if paused else "media-playback-pause-symbolic"
        )
        if snapshot.state == AppState.DELETE_REVIEW:
            self.sync_content.set_label(_("Review Deletions"))
            self.sync_content.set_icon_name("security-high-symbolic")
        elif snapshot.state == AppState.KEYRING_LOCKED:
            self.sync_content.set_label(_("Unlock Password Keyring"))
            self.sync_content.set_icon_name("changes-prevent-symbolic")
        else:
            self.sync_content.set_label(
                _("Sync Once")
                if snapshot.state in {AppState.PAUSED_USER, AppState.PAUSED_BATTERY}
                else _("Sync Now")
            )
            self.sync_content.set_icon_name("emblem-synchronizing-symbolic")
        self.last_row.set_subtitle(self._format_last_sync())

    def _progress_changed(self, progress: SyncProgress | None) -> None:
        if progress is None or progress.path is None:
            self.status_progress.set_visible(False)
            return
        action = {
            "download": _("Downloading"),
            "upload": _("Uploading"),
            "delete": _("Deleting"),
            "conflict": _("Conflict"),
            "synced": _("Synchronized"),
            "skipped": _("Skipped"),
        }.get(progress.action, _("Synchronizing"))
        if progress.processed > 0:
            label = _("{action}: {path} ({count})").format(
                action=action, path=progress.path, count=progress.processed
            )
        else:
            label = _("{action}: {path}").format(action=action, path=progress.path)
        self.status_progress.set_text(label)
        self.status_progress.set_tooltip_text(label)
        self.status_progress.set_visible(True)

    def _format_last_sync(self) -> str:
        value = self.session.runtime.get("last_successful_sync")
        if not value:
            return _("Not yet synchronized")
        try:
            stamp = dt.datetime.fromisoformat(value).astimezone()
            return stamp.strftime("%x %H:%M")
        except (ValueError, TypeError):
            return str(value)

    def _log_line(self, line: str) -> None:
        with self._activity_lock:
            self._pending_activity_lines.append(line)
            if self._activity_idle_source:
                return
            self._activity_idle_source = GLib.idle_add(self._drain_activity)

    def _drain_activity(self) -> bool:
        with self._activity_lock:
            lines = tuple(self._pending_activity_lines)
            self._pending_activity_lines.clear()
            self._activity_idle_source = 0
        if self._disposed:
            return GLib.SOURCE_REMOVE
        self._recent_entries.extend(parse_activity_line(line) for line in lines)
        self._recent_entries = self._recent_entries[-5:]
        self._expanded_activity_entries.intersection_update(
            id(entry) for entry in self._recent_entries
        )
        self._refresh_activity()
        return GLib.SOURCE_REMOVE

    def _activity_row(self, entry: ActivityEntry) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow(activatable=True, selectable=False)
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box.set_margin_top(7)
        box.set_margin_bottom(7)
        box.set_margin_start(12)
        box.set_margin_end(12)
        icon = Gtk.Image(icon_name=entry.icon_name, pixel_size=16)
        icon.set_tooltip_text(self._activity_level_name(entry.level))
        box.append(icon)
        label = Gtk.Label(label=entry.message, xalign=0, hexpand=True)
        label.set_use_markup(False)
        label.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        entry_key = id(entry)
        self._set_activity_label_expanded(
            label, entry_key in self._expanded_activity_entries
        )
        box.append(label)
        row.set_child(box)

        primary_click = Gtk.GestureClick.new()
        primary_click.set_button(Gdk.BUTTON_PRIMARY)
        primary_click.connect(
            "released", self._activity_primary_clicked, label, entry_key
        )
        row.add_controller(primary_click)

        secondary_click = Gtk.GestureClick.new()
        secondary_click.set_button(Gdk.BUTTON_SECONDARY)
        secondary_click.connect(
            "pressed", self._activity_secondary_clicked, row, entry.message
        )
        row.add_controller(secondary_click)
        return row

    @staticmethod
    def _activity_level_name(level: str) -> str:
        return {
            "DEBUG": _("Debug"),
            "INFO": _("Information"),
            "WARNING": _("Warning"),
            "ERROR": _("Error"),
            "CRITICAL": _("Critical"),
        }.get(level, _("Information"))

    @staticmethod
    def _set_activity_label_expanded(label: Gtk.Label, expanded: bool) -> None:
        label.set_single_line_mode(not expanded)
        label.set_lines(-1 if expanded else 1)
        label.set_ellipsize(
            Pango.EllipsizeMode.NONE if expanded else Pango.EllipsizeMode.END
        )
        label.set_wrap(expanded)
        label.set_tooltip_text(None if expanded else label.get_text())

    def _activity_primary_clicked(
        self,
        gesture: Gtk.GestureClick,
        press_count: int,
        _x: float,
        _y: float,
        label: Gtk.Label,
        entry_key: int,
    ) -> None:
        if press_count != 1:
            return
        expanded = entry_key not in self._expanded_activity_entries
        if expanded:
            self._expanded_activity_entries.add(entry_key)
        else:
            self._expanded_activity_entries.discard(entry_key)
        self._set_activity_label_expanded(label, expanded)
        gesture.set_state(Gtk.EventSequenceState.CLAIMED)

    def _activity_secondary_clicked(
        self,
        gesture: Gtk.GestureClick,
        press_count: int,
        x: float,
        y: float,
        row: Gtk.ListBoxRow,
        message: str,
    ) -> None:
        if press_count != 1:
            return
        gesture.set_state(Gtk.EventSequenceState.CLAIMED)

        menu = Gio.Menu()
        menu.append(_("Copy Message"), "activity.copy")
        actions = Gio.SimpleActionGroup()
        copy_action = Gio.SimpleAction.new("copy", None)
        actions.add_action(copy_action)
        row.insert_action_group("activity", actions)

        popover = Gtk.PopoverMenu.new_from_model(menu)
        popover.set_has_arrow(True)
        popover.set_parent(row)
        target = Gdk.Rectangle()
        target.x = int(x)
        target.y = int(y)
        target.width = 1
        target.height = 1
        popover.set_pointing_to(target)
        copy_action.connect(
            "activate", self._copy_activity_message, message, popover
        )
        popover.connect("closed", self._activity_menu_closed, row)
        popover.popup()

    def _copy_activity_message(
        self,
        _action: Gio.SimpleAction,
        _parameter: GLib.Variant | None,
        message: str,
        popover: Gtk.PopoverMenu,
    ) -> None:
        self.get_clipboard().set(message)
        popover.popdown()
        self._show_toast(_("Message copied"))

    def _show_toast(self, title: str) -> None:
        overlay = self.get_ancestor(Adw.ToastOverlay)
        if overlay:
            overlay.add_toast(Adw.Toast(title=title))

    @staticmethod
    def _activity_menu_closed(
        popover: Gtk.PopoverMenu, row: Gtk.ListBoxRow
    ) -> None:
        row.insert_action_group("activity", None)
        popover.unparent()

    def _empty_activity_row(self) -> Gtk.ListBoxRow:
        return self._activity_row(
            ActivityEntry(
                level=_("Information"),
                message=_("No activity in this session"),
                icon_name="dialog-information-symbolic",
            )
        )

    def _refresh_activity(self) -> None:
        for row in self._activity_rows:
            self.activity_expander.remove(row)
        self._activity_rows.clear()
        entries = list(reversed(self._recent_entries))
        if entries:
            count = len(entries)
            subtitle = (
                _("1 event in this session")
                if count == 1
                else _("{count} events in this session").format(count=count)
            )
            self.activity_expander.set_subtitle(subtitle)
            rows = [self._activity_row(entry) for entry in entries]
        else:
            self.activity_expander.set_subtitle(_("No activity in this session"))
            rows = [self._empty_activity_row()]
        rows.append(self.view_log_row)
        rows.append(self.conflicts_row)
        for row in rows:
            self.activity_expander.add_row(row)
        self._activity_rows.extend(rows)

    def _sync_clicked(self, _button: Gtk.Button) -> None:
        if self.runtime.scheduler.delete_alert:
            application = self.application
            if application and hasattr(application, "review_delete_alert"):
                application.review_delete_alert(self)
            return
        if self.runtime.scheduler.battery_paused:
            dialog = Adw.AlertDialog(
                heading=_("Synchronization is paused on battery"),
                body=_("Run one synchronization without changing the power preference?"),
            )
            dialog.add_response("cancel", _("Cancel"))
            dialog.add_response("sync", _("Sync Once"))
            dialog.set_response_appearance("sync", Adw.ResponseAppearance.SUGGESTED)
            dialog.choose(self, None, self._battery_choice)
            return
        self.runtime.sync_now()

    def _battery_choice(self, dialog: Adw.AlertDialog, result: Gio.AsyncResult) -> None:
        if dialog.choose_finish(result) == "sync":
            self.runtime.sync_now()

    def _pause_clicked(self, _button: Gtk.Button) -> None:
        self.runtime.set_paused(not self.runtime.scheduler.user_paused)

    def open_folder(self, folder: object | None = None) -> None:
        if folder is not None:
            root = Path(getattr(folder, "local_root", str(folder)))
        elif self.session.folders:
            root = Path(self.session.folders[0].local_root)
        else:
            return
        root.mkdir(parents=True, exist_ok=True)
        Gio.AppInfo.launch_default_for_uri(root.as_uri(), None)

    def show_log(self, _button: Gtk.Button | None = None) -> None:
        if self._disposed:
            return
        if not self.log_window:
            self.log_window = LogWindow(self, self.logger)
            self.log_window.connect("close-request", self._log_closed)
        self.log_window.present()

    def _show_conflicts(self) -> None:
        application = self.application
        if application and hasattr(application, "show_conflicts"):
            application.show_conflicts()

    def _log_closed(self, _window: Gtk.Window) -> bool:
        self.log_window = None
        return False

    def dispose(self) -> None:
        if self._disposed:
            return
        self._disposed = True
        self._state_unsubscribe()
        self._progress_unsubscribe()
        self._log_unsubscribe()
        if self._activity_idle_source:
            GLib.source_remove(self._activity_idle_source)
            self._activity_idle_source = 0
        with self._activity_lock:
            self._pending_activity_lines.clear()
        if self.log_window:
            self.log_window.close()
            self.log_window = None


class MainWindow(Adw.ApplicationWindow):
    def __init__(
        self,
        application: Gtk.Application,
        config: object,
        account_manager: object,
        logger: object,
        *,
        on_add_account: Callable[[], None] | None = None,
        on_open_settings: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(application=application, title=APP_NAME)
        self.set_default_size(900, 600)
        self.config = config
        self.account_manager = account_manager
        self.logger = logger
        self._on_add_account = on_add_account
        self._on_open_settings = on_open_settings
        self.account_view: AccountView | None = None
        self.account_rows: dict[str, Gtk.ListBoxRow] = {}
        self._disposed = False
        self._selecting = False

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.set_title_widget(Adw.WindowTitle(title=APP_NAME, subtitle=_("Nextcloud file synchronization")))
        settings = Gtk.Button(
            icon_name="emblem-system-symbolic", tooltip_text=_("Settings"), css_classes=["flat"]
        )
        settings.connect("clicked", self.show_settings)
        header.pack_end(settings)
        about = Gtk.Button(
            icon_name="help-about-symbolic", tooltip_text=_("About"), css_classes=["flat"]
        )
        about.connect("clicked", self._show_about)
        header.pack_end(about)
        toolbar.add_top_bar(header)

        self.toast_overlay = Adw.ToastOverlay()

        split = Adw.NavigationSplitView()
        split.set_collapsed(False)
        split.set_sidebar_width_fraction(0.28)
        split.set_min_sidebar_width(220)

        sidebar = self._build_sidebar()
        self.content_stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        clamp = Adw.Clamp(maximum_size=660, tightening_threshold=500)
        clamp.set_child(self.content_stack)
        scroller.set_child(clamp)
        self.toast_overlay.set_child(scroller)
        split.set_content(sidebar=sidebar, content=self.toast_overlay)

        toolbar.set_content(split)
        self.set_content(toolbar)
        self.connect("close-request", self._hide_on_close)

    def _build_sidebar(self) -> Gtk.Widget:
        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        sidebar.set_margin_top(12)
        sidebar.set_margin_bottom(12)
        sidebar.set_margin_start(6)
        sidebar.set_margin_end(6)

        label = Gtk.Label(label=_("Accounts"), xalign=0, css_classes=["heading"])
        label.set_margin_start(8)
        label.set_margin_bottom(4)
        sidebar.append(label)

        self.accounts_list = Gtk.ListBox(
            css_classes=["boxed-list", "navigation-sidebar"], selection_mode=Gtk.SelectionMode.SINGLE
        )
        self.accounts_list.connect("row-selected", self._account_selected)
        sidebar.append(self.accounts_list)

        add_button = Gtk.Button(
            label=_("Add Account"), icon_name="list-add-symbolic",
            halign=Gtk.Align.FILL, css_classes=["flat"],
        )
        add_button.connect("clicked", lambda _button: self._add_account())
        sidebar.append(add_button)
        return sidebar

    def _refresh_sidebar(self) -> None:
        while row := self.accounts_list.get_first_child():
            self.accounts_list.remove(row)
        self.account_rows.clear()
        for account in self.config.accounts:
            row = Gtk.ListBoxRow(activatable=True, selectable=True)
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            box.set_margin_top(8)
            box.set_margin_bottom(8)
            box.set_margin_start(8)
            box.set_margin_end(8)
            avatar = Gtk.Image(icon_name="avatar-default-symbolic", pixel_size=28)
            box.append(avatar)
            text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
            name = Gtk.Label(label=account["login_name"], xalign=0, ellipsize=Pango.EllipsizeMode.END)
            server = Gtk.Label(
                label=account["server_url"], xalign=0, ellipsize=Pango.EllipsizeMode.END,
                css_classes=["dim-label"],
            )
            text.append(name)
            text.append(server)
            box.append(text)
            row.set_child(box)
            row.data = account
            self.accounts_list.append(row)
            self.account_rows[account["id"]] = row

    def _account_selected(self, listbox: Gtk.ListBox, row: Gtk.ListBoxRow | None) -> None:
        if self._selecting or row is None:
            return
        account = getattr(row, "data", None)
        if not account:
            return
        application = self.get_application()
        if application and hasattr(application, "set_active_account"):
            application.set_active_account(account["id"])
        self._show_account(account["id"])

    def _show_account(self, account_id: str | None) -> None:
        if self.account_view:
            self.account_view.dispose()
            self.account_view = None
        if not account_id or not self.account_manager:
            self.content_stack.set_visible_child_name("empty")
            return
        runtime = self.account_manager.get(account_id)
        if not runtime:
            self.content_stack.set_visible_child_name("empty")
            return
        session = runtime.session
        view = AccountView(
            self.get_application(),
            self.config,
            session,
            runtime,
            self.logger,
        )
        self.account_view = view
        self.content_stack.add_named(view, "account")
        self.content_stack.set_visible_child_name("account")

    def _add_account(self) -> None:
        if self._on_add_account:
            self._on_add_account()

    def present_account(self, account_id: str | None) -> None:
        self._refresh_sidebar()
        if not account_id and self.config.accounts:
            account_id = self.config.accounts[0]["id"]
        self._selecting = True
        try:
            for row_id, row in self.account_rows.items():
                if row_id == account_id:
                    self.accounts_list.select_row(row)
                    break
            else:
                self.accounts_list.select_row(None)
        finally:
            self._selecting = False
        self._show_account(account_id)

    def show_log(self, _button: Gtk.Button | None = None) -> None:
        if self._disposed:
            return
        if self.account_view:
            self.account_view.show_log()

    def show_settings(self, _button: Gtk.Button | None = None) -> None:
        if self._disposed:
            return
        if self._on_open_settings:
            self._on_open_settings()
        else:
            application = self.get_application()
            if application and hasattr(application, "show_settings"):
                application.show_settings()

    def open_folder(self) -> None:
        if self.account_view:
            self.account_view.open_folder()

    def _show_about(self, _button: Gtk.Button) -> None:
        application = self.get_application()
        check_for_updates = (
            application.check_for_updates
            if application and hasattr(application, "check_for_updates")
            else None
        )
        show_about_dialog(self, check_for_updates)

    def _hide_on_close(self, _window: Gtk.Window) -> bool:
        self._dispose_ui()
        application = self.get_application()
        if application:
            application.main_window_closed(self)
        return False

    def _dispose_ui(self) -> None:
        if self._disposed:
            return
        self._disposed = True
        if self.account_view:
            self.account_view.dispose()
            self.account_view = None

    def dispose_for_account_reset(self) -> None:
        self._dispose_ui()
        self.set_visible(False)
