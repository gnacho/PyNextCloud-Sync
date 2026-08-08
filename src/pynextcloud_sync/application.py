from __future__ import annotations

from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from pynextcloud_sync import APP_ID
from pynextcloud_sync.core.desktop_integration import DesktopIntegration
from pynextcloud_sync.core.runtime import RuntimeController
from pynextcloud_sync.nextcloud.credentials import CredentialStore
from pynextcloud_sync.nextcloud.api import NextcloudApi
from pynextcloud_sync.storage.config import ConfigStore, ConfigurationError
from pynextcloud_sync.storage.log import AppLogger
from pynextcloud_sync.ui.main_window import MainWindow
from pynextcloud_sync.ui.settings import SettingsWindow
from pynextcloud_sync.ui.setup import SetupWindow
from pynextcloud_sync.ui.tray import StatusNotifier
from pynextcloud_sync.util.i18n import _
from pynextcloud_sync.util.paths import project_root


class PyNextCloudApplication(Adw.Application):
    def __init__(self, background: bool = False) -> None:
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.background = background
        self._activation_count = 0
        self.config = ConfigStore()
        self.logger = AppLogger()
        self.credentials = CredentialStore(logger=self.logger)
        self.runtime: RuntimeController | None = None
        self.desktop_integration: DesktopIntegration | None = None
        self.main_window: MainWindow | None = None
        self.settings_window: SettingsWindow | None = None
        self.setup_window: SetupWindow | None = None
        self.tray: StatusNotifier | None = None

    def do_startup(self) -> None:
        Adw.Application.do_startup(self)
        self.hold()
        try:
            self.config.load()
        except ConfigurationError as exc:
            self.logger.error(exc)
            self.config.data["account"] = None
        logging_config = self.config.data["logging"]
        self.logger.configure(
            save_to_disk=logging_config["save_logs"],
            retention_days=logging_config["retention_days"],
        )
        self._install_actions()

    def _install_actions(self) -> None:
        for name, callback in (
            ("show", lambda *_args: self.present_main()),
            ("sync", lambda *_args: self.runtime.sync_now() if self.runtime else None),
            ("log", lambda *_args: self.show_log()),
            ("settings", lambda *_args: self.show_settings()),
            ("quit", lambda *_args: self.request_quit()),
        ):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)

    def do_activate(self) -> None:
        first_activation = self._activation_count == 0
        self._activation_count += 1
        display = Gdk.Display.get_default()
        if display:
            theme = Gtk.IconTheme.get_for_display(display)
            theme.add_search_path(str(project_root() / "data" / "icons"))
            theme.add_search_path(str(project_root() / "data" / "icons" / "status"))
        if not self.config.configured:
            if not self.setup_window:
                self.setup_window = SetupWindow(
                    self, self.config, self.credentials, self._setup_complete
                )
            self.setup_window.present()
            return
        self._ensure_desktop_integration()
        self._ensure_runtime()
        self._ensure_tray()
        if not (first_activation and self.background):
            self.present_main()

    def _setup_complete(self) -> None:
        if self.setup_window:
            old_setup = self.setup_window
            old_setup.set_visible(False)
            self.remove_window(old_setup)
            self.setup_window = None
        self._ensure_desktop_integration()
        if self.desktop_integration:
            results = self.desktop_integration.initialize_defaults()
            failed = [name for name, succeeded in results.items() if not succeeded]
            if failed:
                self.logger.warning(
                    "Could not initialize desktop integrations: %s", ", ".join(failed)
                )
        self._ensure_runtime()
        self._ensure_tray()
        self.present_main()

    def _ensure_runtime(self) -> None:
        if self.runtime:
            return
        self.runtime = RuntimeController(
            self.config, self.credentials, self.logger, self._notify_sync_failure
        )
        self.runtime.start()

    def _ensure_desktop_integration(self) -> None:
        account = self.config.data.get("account")
        if not account:
            return
        root = Path(account["local_root"])
        if (
            self.desktop_integration
            and self.desktop_integration.sync_root != root.expanduser().absolute()
        ):
            self.desktop_integration.close()
            self.desktop_integration = None
        if not self.desktop_integration:
            self.desktop_integration = DesktopIntegration(root)

    def _ensure_tray(self) -> None:
        if self.tray or not self.runtime:
            return
        self.tray = StatusNotifier(
            self.runtime.state,
            self.present_main,
            self.runtime.sync_now,
            lambda: self.runtime.set_paused(not self.runtime.scheduler.user_paused),
            self.open_folder,
            self.show_log,
            self.show_settings,
            self.request_quit,
            self.logger,
        )
        self.tray.start()

    def _ensure_main_window(self) -> None:
        if self.main_window or not self.runtime:
            return
        self.main_window = MainWindow(self, self.config, self.runtime, self.logger)

    def present_main(self) -> None:
        if not self.config.configured:
            self.activate()
            return
        self._ensure_runtime()
        self._ensure_tray()
        self._ensure_main_window()
        if self.main_window:
            self.main_window.unminimize()
            self.main_window.present()

    def open_folder(self) -> None:
        account = self.config.data.get("account")
        if not account:
            return
        root = Path(account["local_root"])
        root.mkdir(parents=True, exist_ok=True)
        Gio.AppInfo.launch_default_for_uri(root.as_uri(), None)

    def show_log(self) -> None:
        if not self.config.configured:
            self.activate()
            return
        self._ensure_runtime()
        self._ensure_tray()
        self._ensure_main_window()
        if self.main_window:
            self.main_window.show_log()

    def show_settings(self) -> None:
        if not self.config.configured:
            self.activate()
            return
        self._ensure_runtime()
        self._ensure_tray()
        self._ensure_desktop_integration()
        if not self.runtime or not self.desktop_integration:
            return
        if not self.settings_window:
            self.settings_window = SettingsWindow(
                self,
                self.config,
                self.runtime,
                self.desktop_integration,
                self.remove_account,
            )
            self.settings_window.connect("close-request", self._settings_window_closed)
        self.settings_window.unminimize()
        self.settings_window.present()

    def _settings_window_closed(self, window: SettingsWindow) -> bool:
        if self.settings_window is window:
            self.settings_window = None
        return False

    def main_window_closed(self, window: MainWindow) -> None:
        if self.main_window is window:
            self.main_window = None

    def _notify_sync_failure(self, result: object) -> None:
        if getattr(result, "classification", "") == "authentication":
            notification = Gio.Notification.new(_("Nextcloud account needs attention"))
            notification.set_body(_("Open PyNextCloud Sync to check the account credential."))
            notification.set_default_action("app.show")
            self.send_notification("auth-failure", notification)
        else:
            notification = Gio.Notification.new(_("Synchronization failed"))
            retries = self.config.data["sync"]["max_sync_retries"]
            notification.set_body(
                _("Synchronization failed after {retries} retries. Open the log for details.").format(
                    retries=retries
                )
            )
            notification.set_default_action("app.log")
            self.send_notification("sync-failure", notification)

    def request_quit(self) -> None:
        if self.runtime and self.runtime.engine.running:
            notification = Gio.Notification.new(_("Finishing synchronization"))
            notification.set_body(
                _("PyNextCloud Sync will quit when the current synchronization finishes.")
            )
            self.send_notification("quit-pending", notification)
            GLib.timeout_add_seconds(1, self._quit_when_ready)
            return
        self.quit()

    def remove_account(self) -> None:
        account = self.config.data.get("account")
        if not account:
            return

        def finalize() -> None:
            if self.settings_window:
                old_settings = self.settings_window
                self.settings_window = None
                old_settings.close()
            if self.tray:
                self.tray.stop()
                self.tray = None
            if self.runtime:
                self.runtime.stop()
                self.runtime = None
            if self.desktop_integration:
                self.desktop_integration.cleanup()
                self.desktop_integration.close()
                self.desktop_integration = None
            if self.main_window:
                old_window = self.main_window
                old_window.dispose_for_account_reset()
                self.remove_window(old_window)
                self.main_window = None
            self.config.reset_account()
            self.setup_window = SetupWindow(
                self, self.config, self.credentials, self._setup_complete
            )
            self.setup_window.present()

        def cleared(_ok: bool, _error: Exception | None) -> None:
            finalize()

        def secret_ready(password: str | None, _error: Exception | None) -> None:
            def clear_local(_revoked: bool = False) -> None:
                self.credentials.clear(
                    account["server_url"], account["login_name"], cleared
                )

            if password:
                NextcloudApi().revoke_app_password(
                    account["server_url"], account["login_name"], password, clear_local
                )
            else:
                clear_local()

        self.credentials.lookup(
            account["server_url"], account["login_name"], secret_ready
        )

    def _quit_when_ready(self) -> bool:
        if self.runtime and self.runtime.engine.running:
            return GLib.SOURCE_CONTINUE
        self.quit()
        return GLib.SOURCE_REMOVE

    def do_shutdown(self) -> None:
        if self.settings_window:
            self.settings_window.close()
        if self.tray:
            self.tray.stop()
        if self.runtime:
            self.runtime.stop()
        if self.desktop_integration:
            self.desktop_integration.close()
        self.logger.close()
        Adw.Application.do_shutdown(self)
