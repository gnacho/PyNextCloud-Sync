from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]


def method_source(path: Path, class_name: str, method_name: str) -> str:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for member in node.body:
                if isinstance(member, ast.FunctionDef) and member.name == method_name:
                    return ast.get_source_segment(source, member) or ""
    raise AssertionError(f"{class_name}.{method_name} was not found")


class LifecycleContractTests(unittest.TestCase):
    def test_background_activation_keeps_the_main_window_lazy(self) -> None:
        path = ROOT / "src" / "pynextcloud_sync" / "application.py"
        activate = method_source(path, "PyNextCloudApplication", "do_activate")
        continue_activation = method_source(
            path, "PyNextCloudApplication", "_continue_activation"
        )
        self.assertIn("self._begin_startup_update_check()", activate)
        self.assertIn("self._ensure_tray()", continue_activation)
        self.assertNotIn("self._ensure_main_window()", activate)

    def test_update_check_precedes_runtime_and_mandatory_updates_block_it(self) -> None:
        path = ROOT / "src" / "pynextcloud_sync" / "application.py"
        activate = method_source(path, "PyNextCloudApplication", "do_activate")
        finished = method_source(
            path, "PyNextCloudApplication", "_startup_update_finished"
        )
        ensure_runtime = method_source(
            path, "PyNextCloudApplication", "_ensure_runtime"
        )
        self.assertIn("if not self._startup_update_complete", activate)
        self.assertIn("result.latest.mandatory", finished)
        self.assertIn("self._enter_mandatory_update_mode", finished)
        self.assertIn("self._continue_activation", finished)
        self.assertIn("self._mandatory_update_manifest", ensure_runtime)

    def test_about_exposes_the_manual_update_check(self) -> None:
        about = (ROOT / "src" / "pynextcloud_sync" / "ui" / "about.py").read_text(
            encoding="utf-8"
        )
        main_window = (
            ROOT / "src" / "pynextcloud_sync" / "ui" / "main_window.py"
        ).read_text(encoding="utf-8")
        self.assertIn('about.add_link(_("Check for Updates")', about)
        self.assertIn('about.connect("activate-link"', about)
        self.assertIn("application.check_for_updates", main_window)

    def test_update_notice_is_a_full_window_with_native_expandable_changelog(self) -> None:
        source = (
            ROOT / "src" / "pynextcloud_sync" / "ui" / "update_window.py"
        ).read_text(encoding="utf-8")
        self.assertIn("class UpdateWindow(Adw.ApplicationWindow)", source)
        self.assertIn("Adw.ExpanderRow(", source)
        self.assertIn("changelog.set_expanded(False)", source)
        self.assertNotIn("Adw.AlertDialog", source)

    def test_update_actions_are_fixed_before_the_scrollable_details(self) -> None:
        source = (
            ROOT / "src" / "pynextcloud_sync" / "ui" / "update_window.py"
        ).read_text(encoding="utf-8")
        self.assertLess(
            source.index('Gtk.Button(label=_("Download New Version"))'),
            source.index("scroller = Gtk.ScrolledWindow("),
        )
        self.assertIn("page.append(scroller)", source)
        self.assertNotIn('_("Open Releases Page")', source)

    def test_update_notice_stays_above_the_main_window(self) -> None:
        path = ROOT / "src" / "pynextcloud_sync" / "application.py"
        show_update = method_source(
            path, "PyNextCloudApplication", "_show_update_window"
        )
        present_main = method_source(path, "PyNextCloudApplication", "present_main")
        self.assertIn("parent=parent", show_update)
        self.assertIn("GLib.idle_add(self._present_update_window_foreground", show_update)
        self.assertIn("self.update_window.set_transient_for(self.main_window)", present_main)
        self.assertIn("self._present_update_window_foreground", present_main)

    def test_mandatory_notice_uses_urgent_copy_and_disables_not_now(self) -> None:
        source = (
            ROOT / "src" / "pynextcloud_sync" / "ui" / "update_window.py"
        ).read_text(encoding="utf-8")
        self.assertIn('"dialog-warning-symbolic"', source)
        self.assertIn('_("Mandatory update available")', source)
        self.assertIn("not_now.set_sensitive(False)", source)
        self.assertIn('Gtk.Button(label=_("Close Application"))', source)

    def test_tray_settings_opens_an_independent_preferences_window(self) -> None:
        application = ROOT / "src" / "pynextcloud_sync" / "application.py"
        main_window = ROOT / "src" / "pynextcloud_sync" / "ui" / "main_window.py"
        settings = ROOT / "src" / "pynextcloud_sync" / "ui" / "settings.py"
        app_settings = method_source(
            application, "PyNextCloudApplication", "show_settings"
        )
        window_settings = method_source(main_window, "MainWindow", "show_settings")
        settings_source = settings.read_text(encoding="utf-8")
        self.assertIn("SettingsWindow(", app_settings)
        self.assertIn("self.settings_window.present()", app_settings)
        self.assertNotIn("self.present_main()", app_settings)
        self.assertNotIn("self._ensure_main_window()", app_settings)
        self.assertIn("application.show_settings()", window_settings)
        self.assertIn(
            "class SettingsWindow(Adw.PreferencesWindow)", settings_source
        )

    def test_desktop_integrations_are_initialized_only_after_new_setup(self) -> None:
        application = ROOT / "src" / "pynextcloud_sync" / "application.py"
        setup_complete = method_source(
            application, "PyNextCloudApplication", "_setup_complete"
        )
        bootstrap_complete = method_source(
            application, "PyNextCloudApplication", "_bootstrap_complete"
        )
        ensure_integration = method_source(
            application, "PyNextCloudApplication", "_ensure_desktop_integration"
        )
        self.assertIn("initialize_integrations=True", setup_complete)
        self.assertIn("initialize_defaults()", bootstrap_complete)
        self.assertNotIn("initialize_defaults()", ensure_integration)

    def test_existing_configuration_requires_bootstrap_before_runtime(self) -> None:
        application = ROOT / "src" / "pynextcloud_sync" / "application.py"
        activate = method_source(
            application, "PyNextCloudApplication", "_continue_activation"
        )
        ensure_runtime = method_source(
            application, "PyNextCloudApplication", "_ensure_runtime"
        )
        self.assertIn('"bootstrap_complete", False', activate)
        self.assertIn("self._ensure_bootstrap()", activate)
        self.assertIn('"bootstrap_complete", False', ensure_runtime)

    def test_closed_main_window_releases_ui_subscriptions(self) -> None:
        path = ROOT / "src" / "pynextcloud_sync" / "ui" / "main_window.py"
        close_handler = method_source(path, "MainWindow", "_hide_on_close")
        dispose = method_source(path, "MainWindow", "_dispose_ui")
        self.assertIn("self._dispose_ui()", close_handler)
        self.assertIn("self._state_unsubscribe()", dispose)
        self.assertIn("self._log_unsubscribe()", dispose)

    def test_log_and_sync_output_have_explicit_memory_limits(self) -> None:
        log_view = (ROOT / "src" / "pynextcloud_sync" / "ui" / "log_view.py").read_text(
            encoding="utf-8"
        )
        sync_engine = (
            ROOT / "src" / "pynextcloud_sync" / "core" / "sync_engine.py"
        ).read_text(encoding="utf-8")
        self.assertIn("MAX_BUFFER_LINES = 2_000", log_view)
        self.assertIn("BoundedOutputCapture(max_lines=200)", sync_engine)

    def test_login_polling_allows_only_one_request_in_flight(self) -> None:
        path = ROOT / "src" / "pynextcloud_sync" / "nextcloud" / "login_flow.py"
        poll = method_source(path, "LoginFlowV2", "_poll")
        cancel = method_source(path, "LoginFlowV2", "cancel")
        self.assertIn("if self._poll_in_flight", poll)
        self.assertIn("self._poll_cancellable.cancel()", cancel)

    def test_manual_keyring_unlock_reconnects_push_and_sync_together(self) -> None:
        path = ROOT / "src" / "pynextcloud_sync" / "core" / "runtime.py"
        sync_now = method_source(path, "RuntimeController", "sync_now")
        self.assertIn("self.scheduler.keyring_locked", sync_now)
        self.assertIn("self.scheduler.request(Trigger.MANUAL)", sync_now)
        self.assertIn("self._configure_push(", sync_now)


if __name__ == "__main__":
    unittest.main()
