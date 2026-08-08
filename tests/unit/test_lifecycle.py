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
        self.assertIn("self._ensure_tray()", activate)
        self.assertNotIn("self._ensure_main_window()", activate)

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
        activate = method_source(application, "PyNextCloudApplication", "do_activate")
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
