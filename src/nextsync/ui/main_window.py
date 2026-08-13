from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Callable, Sequence

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Pango

from nextsync import APP_NAME
from nextsync.core.account import AccountSession
from nextsync.core.state import AppState, StateSnapshot
from nextsync.util.i18n import _

from .about import show_about_dialog
from .folder_status import (
    FolderStatusRow,
    pair_folder_runtimes,
)
from .log_view import LogWindow
from .settings import ExclusionsDialog


def _compact_action_row(**properties: object) -> Adw.ActionRow:
    row = Adw.ActionRow(**properties)
    if hasattr(row, "set_title_lines"):
        row.set_title_lines(1)
    if hasattr(row, "set_subtitle_lines"):
        row.set_subtitle_lines(1)
    return row


class AccountView(Gtk.Box):
    """The synchronization panel for one account.

    Focused on the synchronized folders, like the official / OpenCloud desktop
    clients: one row per folder with its own live status (a check when
    synchronized) and a more (…) menu, plus the global Sync Now / Pause
    buttons. Account management lives in Settings.
    """

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
        self._disposed = False
        self._folder_rows: list[FolderStatusRow] = []

        self.set_margin_top(16)
        self.set_margin_bottom(16)
        self.set_margin_start(18)
        self.set_margin_end(18)

        account_list = Gtk.ListBox(css_classes=["boxed-list"], selection_mode=Gtk.SelectionMode.NONE)
        self.account_list = account_list
        if self.session.folders:
            for folder, folder_runtime in pair_folder_runtimes(
                self.session.folders, self.runtime.folders
            ):
                state_controller = (
                    folder_runtime.state if folder_runtime is not None else None
                )
                folder_row = FolderStatusRow(
                    folder,
                    state_controller,
                    on_open=lambda _folder=folder: self.open_folder(_folder),
                    format_last_sync=lambda _runtime=folder_runtime: self._format_folder_last_sync(
                        _runtime
                    ),
                    on_edit_ignored=self._edit_ignored,
                    on_force_sync=(
                        lambda _fr=folder_runtime: self._force_folder_sync(_fr)
                    ),
                    on_toggle_pause=(
                        lambda _fr=folder_runtime: self._toggle_folder_pause(_fr)
                    ),
                    on_remove=(
                        lambda _folder=folder, _fr=folder_runtime: self._remove_folder(
                            _folder, _fr
                        )
                    ),
                    is_paused=(
                        lambda _fr=folder_runtime: bool(
                            _fr.runtime.scheduler.user_paused
                        )
                        if _fr is not None
                        else False
                    ),
                )
                self._folder_rows.append(folder_row)
                account_list.append(folder_row)
        else:
            account_list.append(
                _compact_action_row(
                    title=_("No Synchronization Folders"),
                    subtitle=_("Add folders from Settings"),
                    icon_name="folder-symbolic",
                )
            )
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

        if hasattr(Adw, "Breakpoint") and hasattr(self, "add_breakpoint"):
            condition = Adw.BreakpointCondition.parse("max-width: 520px")
            breakpoint = Adw.Breakpoint.new(condition)
            breakpoint.add_setter(self.buttons, "orientation", Gtk.Orientation.VERTICAL)
            breakpoint.add_setter(self, "margin-start", 9)
            breakpoint.add_setter(self, "margin-end", 9)
            self.add_breakpoint(breakpoint)

        self._state_unsubscribe = self.runtime.state.subscribe(self._state_changed)

    def _state_changed(self, snapshot: StateSnapshot) -> None:
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

    @staticmethod
    def _format_sync_stamp(value: object) -> str:
        if not value:
            return _("Not yet synchronized")
        try:
            stamp = dt.datetime.fromisoformat(value).astimezone()
            return stamp.strftime("%x %H:%M")
        except (ValueError, TypeError):
            return str(value)

    def _format_folder_last_sync(self, folder_runtime: object | None) -> str:
        session = getattr(folder_runtime, "session", None)
        value = session.runtime.get("last_successful_sync") if session else None
        return self._format_sync_stamp(value)

    def _edit_ignored(self) -> None:
        dialog = ExclusionsDialog(self.config, self.runtime.reconfigure)
        dialog.present(self.get_root() or self)

    def _force_folder_sync(self, folder_runtime: object | None) -> None:
        if folder_runtime is None:
            return
        folder_runtime.runtime.sync_now()

    def _toggle_folder_pause(self, folder_runtime: object | None) -> None:
        if folder_runtime is None:
            return
        folder_runtime.runtime.set_paused(
            not folder_runtime.runtime.scheduler.user_paused
        )

    def _remove_folder(self, folder: object, folder_runtime: object | None) -> None:
        folder_id = getattr(folder, "folder_id", None)
        if not folder_id:
            return
        dialog = Adw.AlertDialog(
            heading=_("Remove this folder from synchronization?"),
            body=_("The local folder and all files inside it will remain untouched."),
        )
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("remove", _("Remove Synchronization"))
        dialog.set_response_appearance("remove", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.choose(self, None, self._remove_folder_choice, folder_id)

    def _remove_folder_choice(
        self, dialog: Adw.AlertDialog, result: Gio.AsyncResult, folder_id: str
    ) -> None:
        if dialog.choose_finish(result) != "remove":
            return
        account_id = self.session.account_id
        try:
            self.config.remove_folder(account_id, folder_id)
        except Exception:
            self._show_toast(_("Could not remove the folder"))
            return
        application = self.application
        if application and hasattr(application, "present_main"):
            application.present_main()

    def _show_toast(self, title: str) -> None:
        overlay = self.get_ancestor(Adw.ToastOverlay)
        if overlay:
            overlay.add_toast(Adw.Toast(title=title))

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
            self.log_window = LogWindow(self.get_root() or self, self.logger)
            self.log_window.connect("close-request", self._log_closed)
        self.log_window.present()

    def _log_closed(self, _window: Gtk.Window) -> bool:
        self.log_window = None
        return False

    def dispose(self) -> None:
        if self._disposed:
            return
        self._disposed = True
        self._state_unsubscribe()
        for folder_row in self._folder_rows:
            folder_row.dispose()
        self._folder_rows.clear()
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
            icon_name="nextsync-settings-2-symbolic", tooltip_text=_("Settings"), css_classes=["flat"]
        )
        settings.connect("clicked", self.show_settings)
        header.pack_end(settings)
        about = Gtk.Button(
            icon_name="nextsync-info-symbolic", tooltip_text=_("About"), css_classes=["flat"]
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
        split.set_sidebar(Adw.NavigationPage.new(sidebar, _("Accounts")))
        split.set_content(Adw.NavigationPage.new(self.toast_overlay, APP_NAME))

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
