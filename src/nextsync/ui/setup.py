from __future__ import annotations

from pathlib import Path
from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk

from nextsync import APP_NAME
from nextsync.core.autostart import AutostartManager
from nextsync.nextcloud.api import NextcloudApi
from nextsync.nextcloud.command import find_nextcloudcmd
from nextsync.nextcloud.login_flow import LoginFlowResult, LoginFlowV2
from nextsync.storage.config import (
    ConfigurationError,
    normalize_remote_path,
    normalize_server_url,
)
from nextsync.util.i18n import _
from nextsync.util.paths import default_sync_root


class SetupWindow(Adw.ApplicationWindow):
    def __init__(
        self,
        application: Gtk.Application,
        config: object,
        credentials: object,
        on_complete: Callable[[], None],
    ) -> None:
        super().__init__(application=application, title=_("Set Up NextSync"))
        self.set_default_size(620, 650)
        self.connect("close-request", self._on_close_request)
        self.config = config
        self.credentials = credentials
        self.on_complete = on_complete
        self.api = NextcloudApi()
        self.login_flow = LoginFlowV2()
        self.server = ""
        self.username = ""
        self.authentication_type = "manual"
        self.folders: list[dict[str, str]] = []

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar(show_title=False)
        toolbar.add_top_bar(header)
        self.stack = Gtk.Stack(
            transition_type=Gtk.StackTransitionType.SLIDE_LEFT_RIGHT,
            transition_duration=250,
        )
        toolbar.set_content(self.stack)
        self.set_content(toolbar)
        self._build_welcome()
        self._build_server()
        self._build_authentication()
        self._build_folders()
        self._build_summary()
        self.stack.set_visible_child_name("welcome")

    def _on_close_request(self, _window: Adw.ApplicationWindow) -> bool:
        self.get_application().quit()
        return False

    def _page(self) -> tuple[Gtk.Box, Gtk.Box]:
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        clamp = Adw.Clamp(maximum_size=480, tightening_threshold=360, vexpand=True)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        content.set_margin_top(36)
        content.set_margin_bottom(36)
        content.set_margin_start(18)
        content.set_margin_end(18)
        clamp.set_child(content)
        outer.append(clamp)
        return outer, content

    def _build_welcome(self) -> None:
        page, content = self._page()
        status = Adw.StatusPage(
            icon_name="io.github.gnacho.nextsync",
            title=APP_NAME,
            description=_("A lightweight desktop synchronizer for Nextcloud."),
        )
        status.set_vexpand(True)
        content.append(status)
        description = Gtk.Label(
            label=_("Your complete Nextcloud file tree will be stored physically on this computer and synchronized in both directions."),
            wrap=True,
            justify=Gtk.Justification.CENTER,
            css_classes=["dim-label"],
        )
        content.append(description)
        if not find_nextcloudcmd():
            warning = Adw.Banner(
                title=_("nextcloudcmd is missing. Install the nextcloud-desktop-cmd package before the first synchronization."),
                revealed=True,
            )
            content.append(warning)
        start = Gtk.Button(label=_("Get Started"), css_classes=["suggested-action", "pill"], halign=Gtk.Align.CENTER)
        start.connect("clicked", lambda _button: self.stack.set_visible_child_name("server"))
        content.append(start)
        self.stack.add_named(page, "welcome")

    def _build_server(self) -> None:
        page, content = self._page()
        content.append(Gtk.Label(label=_("Connect to Nextcloud"), xalign=0, css_classes=["title-1"]))
        content.append(
            Gtk.Label(
                label=_("Enter the address you normally use to open Nextcloud in a browser."),
                wrap=True,
                xalign=0,
                css_classes=["dim-label"],
            )
        )
        group = Adw.PreferencesGroup()
        self.server_entry = Adw.EntryRow(title=_("Nextcloud server URL"))
        self.server_entry.set_text("https://")
        group.add(self.server_entry)
        self.trust_invalid = Adw.SwitchRow(
            title=_("Allow invalid or self-signed certificates"),
            subtitle=_("This weakens connection security. Enable only for a server you trust."),
        )
        group.add(self.trust_invalid)
        content.append(group)
        self.server_error = Gtk.Label(xalign=0, wrap=True, css_classes=["error"])
        content.append(self.server_error)
        actions = Gtk.Box(spacing=12, homogeneous=True)
        back = Gtk.Button(label=_("Back"))
        back.connect("clicked", lambda _button: self.stack.set_visible_child_name("welcome"))
        actions.append(back)
        next_button = Gtk.Button(label=_("Continue"), css_classes=["suggested-action"])
        next_button.connect("clicked", self._server_continue)
        actions.append(next_button)
        content.append(actions)
        self.stack.add_named(page, "server")

    def _build_authentication(self) -> None:
        page, content = self._page()
        content.append(Gtk.Label(label=_("Sign In"), xalign=0, css_classes=["title-1"]))
        browser_group = Adw.PreferencesGroup()
        browser_row = Adw.ActionRow(
            title=_("Sign in with browser"),
            subtitle=_("Recommended. Supports two-factor authentication."),
            icon_name="web-browser-symbolic",
            activatable=True,
        )
        browser_row.add_suffix(Gtk.Image.new_from_icon_name("go-next-symbolic"))
        browser_row.connect("activated", self._browser_login)
        browser_group.add(browser_row)
        content.append(browser_group)
        self.waiting_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, visible=False)
        self.waiting_box.append(Gtk.Spinner(spinning=True, halign=Gtk.Align.CENTER))
        self.waiting_box.append(
            Gtk.Label(label=_("Waiting for authorization in your browser…"), wrap=True)
        )
        waiting_actions = Gtk.Box(spacing=6, halign=Gtk.Align.CENTER)
        reopen = Gtk.Button(label=_("Open Browser Again"))
        reopen.connect("clicked", lambda _button: self.login_flow.reopen_browser())
        waiting_actions.append(reopen)
        cancel = Gtk.Button(label=_("Cancel"))
        cancel.connect("clicked", self._cancel_browser)
        waiting_actions.append(cancel)
        self.waiting_box.append(waiting_actions)
        content.append(self.waiting_box)

        manual = Adw.PreferencesGroup(title=_("Manual Sign In"))
        self.username_entry = Adw.EntryRow(title=_("Username"))
        self.password_entry = Adw.PasswordEntryRow(title=_("Password or app password"))
        manual.add(self.username_entry)
        manual.add(self.password_entry)
        content.append(manual)
        self.auth_error = Gtk.Label(xalign=0, wrap=True, css_classes=["error"])
        content.append(self.auth_error)
        actions = Gtk.Box(spacing=12, homogeneous=True)
        back = Gtk.Button(label=_("Back"))
        back.connect("clicked", lambda _button: self.stack.set_visible_child_name("server"))
        actions.append(back)
        self.manual_button = Gtk.Button(label=_("Sign In Manually"), css_classes=["suggested-action"])
        self.manual_button.connect("clicked", self._manual_login)
        actions.append(self.manual_button)
        content.append(actions)
        self.stack.add_named(page, "authentication")

    def _build_folders(self) -> None:
        page, content = self._page()
        content.append(Gtk.Label(label=_("Synchronization Folders"), xalign=0, css_classes=["title-1"]))
        content.append(
            Gtk.Label(
                label=_("Choose the local folders to mirror from this account. You can add several, or finish now and add folders later from Settings."),
                wrap=True,
                xalign=0,
                css_classes=["dim-label"],
            )
        )
        self.folder_list = Gtk.ListBox(css_classes=["boxed-list"], selection_mode=Gtk.SelectionMode.NONE)
        content.append(self.folder_list)
        self.folder_error = Gtk.Label(xalign=0, wrap=True, css_classes=["error"])
        content.append(self.folder_error)
        add_row = Adw.ActionRow(
            title=_("Add Folder"),
            subtitle=_("Mirror another local folder from this account"),
            icon_name="folder-new-symbolic",
            activatable=True,
        )
        add_row.add_suffix(Gtk.Image.new_from_icon_name("go-next-symbolic"))
        add_row.connect("activated", self._open_add_folder)
        content.append(add_row)
        actions = Gtk.Box(spacing=12, homogeneous=True)
        back = Gtk.Button(label=_("Back"))
        back.connect("clicked", lambda _button: self.stack.set_visible_child_name("authentication"))
        actions.append(back)
        next_button = Gtk.Button(label=_("Review Setup"), css_classes=["suggested-action"])
        next_button.connect("clicked", self._folders_continue)
        actions.append(next_button)
        content.append(actions)
        self.stack.add_named(page, "folders")

    def _build_summary(self) -> None:
        page, content = self._page()
        content.append(Gtk.Label(label=_("Ready to Synchronize"), xalign=0, css_classes=["title-1"]))
        self.summary_list = Gtk.ListBox(css_classes=["boxed-list"], selection_mode=Gtk.SelectionMode.NONE)
        content.append(self.summary_list)
        self.summary_hint = Gtk.Label(
            label=_("The chosen folders will be mirrored in both directions using the Nextcloud synchronization engine."),
            wrap=True,
            xalign=0,
            css_classes=["dim-label"],
        )
        content.append(self.summary_hint)
        actions = Gtk.Box(spacing=12, homogeneous=True)
        back = Gtk.Button(label=_("Back"))
        back.connect("clicked", lambda _button: self.stack.set_visible_child_name("folders"))
        actions.append(back)
        self.start_button = Gtk.Button(label=_("Start Synchronizing"), css_classes=["suggested-action"])
        self.start_button.connect("clicked", self._start_syncing)
        actions.append(self.start_button)
        content.append(actions)
        self.stack.add_named(page, "summary")

    def _server_continue(self, _button: Gtk.Button) -> None:
        try:
            self.server = normalize_server_url(self.server_entry.get_text())
        except ConfigurationError as exc:
            self.server_error.set_text(str(exc))
            return
        trust = self.trust_invalid.get_active()
        self.api.http.trust_invalid_certificates = trust
        self.login_flow.http.trust_invalid_certificates = trust
        self.server_error.set_text("")
        self.stack.set_visible_child_name("authentication")

    def _browser_login(self, _row: Adw.ActionRow) -> None:
        self.auth_error.set_text("")
        self.waiting_box.set_visible(True)
        self.login_flow.start(self.server, self._browser_finished)

    def _cancel_browser(self, _button: Gtk.Button) -> None:
        self.login_flow.cancel()
        self.waiting_box.set_visible(False)

    def _browser_finished(self, result: LoginFlowResult | None, error: Exception | None) -> None:
        self.waiting_box.set_visible(False)
        if error or not result:
            self.auth_error.set_text(str(error or _("Browser sign-in was cancelled.")))
            return
        try:
            self.server = normalize_server_url(result.server)
        except ConfigurationError as exc:
            self.auth_error.set_text(str(exc))
            return
        self.username = result.login_name
        self.authentication_type = "browser"
        self._store_secret(result.app_password)

    def _manual_login(self, _button: Gtk.Button) -> None:
        username = self.username_entry.get_text().strip()
        password = self.password_entry.get_text()
        if not username or not password:
            self.auth_error.set_text(_("Enter a username and password or app password."))
            return
        self.manual_button.set_sensitive(False)
        self.auth_error.set_text(_("Checking account…"))

        def validated(ok: bool, _display_name: str | None, error: Exception | None) -> None:
            self.manual_button.set_sensitive(True)
            if not ok:
                self.auth_error.set_text(str(error or _("Could not sign in.")))
                return
            self.username = username
            self.authentication_type = "manual"
            self._store_secret(password)

        self.api.validate_credentials(self.server, username, password, validated)

    def _store_secret(self, password: str) -> None:
        self.auth_error.set_text(_("Saving account securely…"))

        def stored(ok: bool, error: Exception | None) -> None:
            if not ok:
                self.auth_error.set_text(str(error or _("Could not store the account password.")))
                return
            self.auth_error.set_text("")
            self.password_entry.set_text("")
            self.stack.set_visible_child_name("folders")

        self.credentials.store(self.server, self.username, password, stored)

    def _open_add_folder(self, _row: Adw.ActionRow) -> None:
        self.folder_error.set_text("")
        dialog = Adw.AlertDialog(
            heading=_("Add Folder"),
            body=_("Choose a local folder and an optional remote folder to mirror from this account."),
        )
        entry_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        local_box = Gtk.Box(spacing=6)
        self.add_local_entry = Adw.EntryRow(title=_("Local folder"))
        self.add_local_entry.set_text(str(default_sync_root()))
        local_box.append(self.add_local_entry)
        choose = Gtk.Button(icon_name="folder-open-symbolic", valign=Gtk.Align.CENTER, css_classes=["flat"])
        choose.connect("clicked", lambda _button: self._choose_folder_for_dialog(self.add_local_entry))
        self.add_local_entry.add_suffix(choose)
        entry_box.append(local_box)
        self.add_remote_entry = Adw.EntryRow(title=_("Remote folder (optional, default /)"))
        self.add_remote_entry.set_text("/")
        entry_box.append(self.add_remote_entry)
        dialog.set_extra_child(entry_box)
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("add", _("Add"))
        dialog.set_response_appearance("add", Adw.ResponseAppearance.SUGGESTED)
        dialog.choose(self, None, self._add_folder_response)

    def _add_folder_response(
        self, dialog: Adw.AlertDialog, result: Gio.AsyncResult
    ) -> None:
        response = dialog.choose_finish(result)
        if response != "add":
            return
        root = Path(self.add_local_entry.get_text()).expanduser()
        if not root.is_absolute():
            self.folder_error.set_text(_("Choose an absolute local folder."))
            return
        try:
            remote = normalize_remote_path(self.add_remote_entry.get_text())
        except ConfigurationError as exc:
            self.folder_error.set_text(str(exc))
            return
        pair = {"local_root": str(root), "remote_path": remote}
        if any(item["local_root"] == pair["local_root"] for item in self.folders):
            self.folder_error.set_text(_("This local folder is already added."))
            return
        self.folders.append(pair)
        self._append_folder_row(pair)

    def _append_folder_row(self, pair: dict[str, str]) -> None:
        remote_label = pair["remote_path"] if pair["remote_path"] else "/"
        row = Adw.ActionRow(
            title=pair["local_root"],
            subtitle=_("Remote: {remote}").format(remote=remote_label),
            icon_name="folder-symbolic",
        )
        remove = Gtk.Button(icon_name="user-trash-symbolic", valign=Gtk.Align.CENTER, css_classes=["flat"])
        remove.connect("clicked", lambda _button, _row=row: self._remove_folder_row(_row))
        row.add_suffix(remove)
        self.folder_list.append(row)
        self.folder_list.show()

    def _remove_folder_row(self, row: Adw.ActionRow) -> None:
        title = row.get_title()
        self.folder_list.remove(row)
        self.folders = [item for item in self.folders if item["local_root"] != title]

    def _choose_folder_for_dialog(self, entry: Adw.EntryRow) -> None:
        dialog = Gtk.FileDialog(title=_("Choose NextCloud Folder"), modal=True)
        initial = Path(entry.get_text()).expanduser()
        if initial.is_dir():
            dialog.set_initial_folder(Gio.File.new_for_path(str(initial)))
        dialog.select_folder(self, None, self._dialog_folder_chosen(entry))

    def _dialog_folder_chosen(self, entry: Adw.EntryRow) -> Callable[[Gtk.FileDialog, Gio.AsyncResult], None]:
        def chosen(dialog: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
            try:
                folder = dialog.select_folder_finish(result)
                if folder and folder.get_path():
                    entry.set_text(folder.get_path())
            except GLib.Error:
                pass

        return chosen

    def _folders_continue(self, _button: Gtk.Button) -> None:
        self.folder_error.set_text("")
        while row := self.summary_list.get_first_child():
            self.summary_list.remove(row)
        self.summary_list.append(Adw.ActionRow(title=_("Server"), subtitle=self.server, icon_name="network-server-symbolic"))
        self.summary_list.append(Adw.ActionRow(title=_("Account"), subtitle=self.username, icon_name="avatar-default-symbolic"))
        if not self.folders:
            self.summary_list.append(
                Adw.ActionRow(
                    title=_("No Folders"),
                    subtitle=_("Connected without synchronization folders. Add them later from Settings."),
                    icon_name="folder-symbolic",
                )
            )
            self.start_button.set_label(_("Finish Setup"))
            self.summary_hint.set_text(
                _("The account will be connected without synchronizing any folder. You can add folders later from Settings.")
            )
        else:
            self.start_button.set_label(_("Start Synchronizing"))
            self.summary_hint.set_text(
                _("The chosen folders will be mirrored in both directions using the Nextcloud synchronization engine.")
            )
            for pair in self.folders:
                remote_label = pair["remote_path"] if pair["remote_path"] else "/"
                self.summary_list.append(
                    Adw.ActionRow(
                        title=_("Local Folder"),
                        subtitle=pair["local_root"],
                        icon_name="folder-symbolic",
                    )
                )
                self.summary_list.append(
                    Adw.ActionRow(
                        title=_("Remote Folder"),
                        subtitle=remote_label,
                        icon_name="folder-remote-symbolic",
                    )
                )
        self.summary_list.append(Adw.ActionRow(title=_("Local Detection"), subtitle=_("Filesystem monitor"), icon_name="folder-saved-search-symbolic"))
        self.summary_list.append(Adw.ActionRow(title=_("Remote Detection"), subtitle=_("Server push + every 10 minutes"), icon_name="network-transmit-receive-symbolic"))
        self.stack.set_visible_child_name("summary")

    def _start_syncing(self, _button: Gtk.Button) -> None:
        if not self.folders:
            self._finish_setup()
            return
        self._confirm_first_sync()

    def _local_folder_is_empty(self, folder: dict[str, str]) -> bool:
        root = Path(folder["local_root"]).expanduser()
        try:
            return not any(root.iterdir())
        except OSError:
            return False

    def _confirm_first_sync(self) -> None:
        self.api.http.trust_invalid_certificates = self.trust_invalid.get_active()

        def on_remote(remote_empty: bool, error: Exception | None) -> None:
            if error:
                self._finish_setup()
                return
            self._show_first_sync_dialog(remote_empty)

        def secret_ready(password: str | None, error: Exception | None) -> None:
            if error or not password:
                self._finish_setup()
                return
            self.api.probe_remote(
                self.server, self.username, password, self.folders[0]["remote_path"], on_remote
            )

        self.credentials.lookup(self.server, self.username, secret_ready)

    def _show_first_sync_dialog(self, remote_empty: bool) -> None:
        account = f"{self.username}@{self.server}"
        local_empty = all(self._local_folder_is_empty(item) for item in self.folders)
        count = len(self.folders)
        folder_label = ", ".join(Path(item["local_root"]).name for item in self.folders)
        if local_empty and remote_empty:
            body = _(
                "Connect {account} and start syncing {count} folder(s) ({folders}) now? "
                "Both sides are empty; synchronization will keep them in sync as empty mirrors."
            ).format(account=account, count=count, folders=folder_label)
        elif local_empty:
            body = _(
                "Connect {account} and start syncing {count} folder(s) ({folders}) now? "
                "The remote folders already contain files; they will be downloaded."
            ).format(account=account, count=count, folders=folder_label)
        elif remote_empty:
            body = _(
                "Connect {account} and start syncing {count} folder(s) ({folders}) now? "
                "The local folders already contain files; they will be uploaded."
            ).format(account=account, count=count, folders=folder_label)
        else:
            body = _(
                "Connect {account} and start syncing {count} folder(s) ({folders}) now? Files "
                "that changed on both sides will be preserved as {conflict} (Nextcloud "
                "conflicted copy <date>).<ext>."
            ).format(account=account, count=count, folders=folder_label, conflict="{name}")
        dialog = Adw.AlertDialog(heading=_("Start Synchronizing?"), body=body)
        dialog.add_response("back", _("Back to setup"))
        dialog.add_response("start", _("Start"))
        dialog.set_response_appearance("start", Adw.ResponseAppearance.SUGGESTED)
        dialog.choose(self, None, self._first_sync_choice)

    def _first_sync_choice(
        self, dialog: Adw.AlertDialog, result: Gio.AsyncResult
    ) -> None:
        response = dialog.choose_finish(result)
        if response == "start":
            self._finish_setup()
        else:
            self.stack.set_visible_child_name("folders")

    def _finish_setup(self) -> None:
        for pair in self.folders:
            Path(pair["local_root"]).expanduser().mkdir(parents=True, exist_ok=True)
        account = {
            "server_url": self.server,
            "login_name": self.username,
            "authentication_type": self.authentication_type,
            "folders": [
                {"local_root": pair["local_root"], "remote_path": pair["remote_path"]}
                for pair in self.folders
            ],
        }
        self.config.data["network"]["trust_invalid_certificates"] = (
            self.trust_invalid.get_active()
        )
        self.config.add_account(account)
        AutostartManager().set_enabled(self.config.data["general"]["autostart"])
        self.on_complete()
