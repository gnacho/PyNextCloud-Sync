from __future__ import annotations

import ast
import importlib.util
import sys
import types
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

from nextsync.core.state import AppState, StateController
from nextsync.ui.tray_state import presentation_for


TRAY_SOURCE = (
    Path(__file__).parents[2]
    / "src"
    / "nextsync"
    / "ui"
    / "tray.py"
)


class FakeVariant:
    def __init__(self, signature: str, value: object) -> None:
        self.signature = signature
        self.value = value

    def unpack(self) -> object:
        return self.value


class FakePixbuf:
    def __init__(self, size: int) -> None:
        self.size = size

    @classmethod
    def new_from_file_at_scale(
        cls, _path: str, width: int, _height: int, _preserve_aspect: bool
    ) -> "FakePixbuf":
        return cls(width)

    def get_pixels(self) -> bytes:
        return bytes((255, 255, 255, 255)) * self.size * self.size

    def get_n_channels(self) -> int:
        return 4

    def get_rowstride(self) -> int:
        return self.size * 4

    def get_has_alpha(self) -> bool:
        return True

    def get_width(self) -> int:
        return self.size

    def get_height(self) -> int:
        return self.size


class FakeConnection:
    def __init__(self) -> None:
        self.signals: list[tuple[object, ...]] = []

    def emit_signal(self, *args: object) -> None:
        self.signals.append(args)


def load_tray_module():
    fake_gi = types.ModuleType("gi")
    fake_gi.require_version = lambda *_args: None
    fake_repository = types.ModuleType("gi.repository")
    fake_repository.GdkPixbuf = types.SimpleNamespace(Pixbuf=FakePixbuf)
    fake_repository.Gio = types.SimpleNamespace()
    fake_repository.GLib = types.SimpleNamespace(Variant=FakeVariant, Error=Exception)
    spec = importlib.util.spec_from_file_location(
        "nextsync_tray_transition_test", TRAY_SOURCE
    )
    module = importlib.util.module_from_spec(spec)
    with patch.dict(
        sys.modules,
        {"gi": fake_gi, "gi.repository": fake_repository},
    ):
        assert spec.loader is not None
        spec.loader.exec_module(module)
    return module


class FakeLogger:
    def warning(self, *_args: object) -> None:
        pass


def assigned_string(name: str) -> str:
    tree = ast.parse(TRAY_SOURCE.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if any(
                isinstance(target, ast.Name) and target.id == name
                for target in node.targets
            ):
                return ast.literal_eval(node.value)
    raise AssertionError(f"{name} was not found")


class TrayContractTests(unittest.TestCase):
    def test_status_notifier_exports_icon_theme_path_on_the_item(self) -> None:
        root = ET.fromstring(assigned_string("ITEM_XML"))
        interface = root.find("./interface[@name='org.kde.StatusNotifierItem']")
        self.assertIsNotNone(interface)
        property_node = interface.find("./property[@name='IconThemePath']")
        self.assertIsNotNone(property_node)
        self.assertEqual(property_node.attrib["type"], "s")
        self.assertEqual(property_node.attrib["access"], "read")

    def test_window_id_uses_the_signed_type_expected_by_gnome_host(self) -> None:
        root = ET.fromstring(assigned_string("ITEM_XML"))
        property_node = root.find(
            "./interface[@name='org.kde.StatusNotifierItem']/property[@name='WindowId']"
        )
        self.assertIsNotNone(property_node)
        self.assertEqual(property_node.attrib["type"], "i")

    def test_tray_publishes_themed_icon_name_and_keeps_pixmap_fallbacks(self) -> None:
        source = TRAY_SOURCE.read_text(encoding="utf-8")
        self.assertIn('"IconName": GLib.Variant("s", icon_name)', source)
        self.assertIn('"IconPixmap": GLib.Variant("a(iiay)", icon_pixmaps)', source)
        self.assertIn("def _find_status_icon(", source)
        self.assertIn("def _load_application_pixmaps(", source)

    def test_every_application_state_has_a_status_asset(self) -> None:
        icon_directory = TRAY_SOURCE.parents[3] / "data" / "icons" / "status"
        for state in AppState:
            with self.subTest(state=state):
                presentation = presentation_for(state)
                icon = (
                    icon_directory
                    / f"nextsync-status-{presentation.icon_key}-symbolic.svg"
                )
                self.assertTrue(icon.is_file(), icon)

    def test_expected_states_use_distinct_icon_presentations(self) -> None:
        expected = {
            AppState.IDLE_OK: "ok",
            AppState.SYNCING: "syncing",
            AppState.SYNC_QUEUED: "syncing",
            AppState.PAUSED_USER: "paused",
            AppState.PAUSED_BATTERY: "battery",
            AppState.OFFLINE: "offline",
            AppState.ERROR: "error",
            AppState.AUTH_REQUIRED: "error",
            AppState.KEYRING_LOCKED: "error",
        }
        for state, icon_key in expected.items():
            with self.subTest(state=state):
                self.assertEqual(presentation_for(state).icon_key, icon_key)

    def test_user_pause_controls_the_resume_menu_label(self) -> None:
        self.assertTrue(presentation_for(AppState.PAUSED_USER).user_paused)
        self.assertFalse(presentation_for(AppState.PAUSED_BATTERY).user_paused)

    def test_state_changes_publish_both_notification_styles(self) -> None:
        source = TRAY_SOURCE.read_text(encoding="utf-8")
        self.assertIn('"org.freedesktop.DBus.Properties"', source)
        self.assertIn('"PropertiesChanged"', source)
        for signal_name in (
            "NewStatus",
            "NewTitle",
            "NewIcon",
            "NewAttentionIcon",
            "NewToolTip",
        ):
            self.assertIn(f'"{signal_name}"', source)

    def test_live_state_transition_changes_the_published_icon(self) -> None:
        tray_module = load_tray_module()
        state = StateController(AppState.IDLE_OK)
        no_op = lambda: None
        notifier = tray_module.StatusNotifier(
            state,
            no_op,
            no_op,
            no_op,
            no_op,
            no_op,
            no_op,
            no_op,
            FakeLogger(),
        )
        connection = FakeConnection()
        notifier.connection = connection

        state.set(AppState.PAUSED_USER, "Synchronization is paused")
        paused_change = next(
            signal
            for signal in connection.signals
            if signal[2] == "org.freedesktop.DBus.Properties"
            and signal[3] == "PropertiesChanged"
        )
        paused_properties = paused_change[4].value[1]
        self.assertEqual(
            paused_properties["IconName"].value,
            "io.github.gnacho.nextsync",
        )
        self.assertEqual(paused_properties["IconThemePath"].value, "")
        self.assertIsInstance(paused_properties["IconPixmap"].value, list)
        self.assertEqual(paused_properties["Status"].value, "Active")

        connection.signals.clear()
        state.set(AppState.SYNCING, "Synchronizing files…")
        syncing_change = next(
            signal
            for signal in connection.signals
            if signal[2] == "org.freedesktop.DBus.Properties"
            and signal[3] == "PropertiesChanged"
        )
        syncing_properties = syncing_change[4].value[1]
        self.assertEqual(
            syncing_properties["IconName"].value,
            "io.github.gnacho.nextsync",
        )
        self.assertIn(
            "NewIcon", [signal[3] for signal in connection.signals]
        )

    def test_menu_is_trimmed_to_open_settings_and_quit(self) -> None:
        tray_module = load_tray_module()
        state = StateController(AppState.IDLE_OK)
        no_op = lambda: None
        notifier = tray_module.StatusNotifier(
            state,
            no_op,
            no_op,
            no_op,
            no_op,
            no_op,
            no_op,
            no_op,
            FakeLogger(),
        )
        layout = notifier._layout_data(0)
        children = [child.unpack()[0] for child in layout[2]]
        self.assertEqual(children, [1, 7, 8])
        expected = {
            1: ("Open NextSync", "window-new-symbolic"),
            7: ("Settings", "nextsync-settings-2-symbolic"),
            8: ("Quit", "application-exit-symbolic"),
        }
        for item_id in children:
            with self.subTest(item_id=item_id):
                props = notifier._properties(item_id)
                label, icon = expected[item_id]
                self.assertEqual(props["label"].value, label)
                self.assertEqual(props["icon-name"].value, icon)
                self.assertTrue(props["enabled"].value)
                self.assertTrue(props["visible"].value)
                self.assertNotIn("type", props)

    def test_actions_table_contains_only_open_settings_quit(self) -> None:
        tray_module = load_tray_module()
        state = StateController(AppState.IDLE_OK)
        no_op = lambda: None
        notifier = tray_module.StatusNotifier(
            state,
            no_op,
            no_op,
            no_op,
            no_op,
            no_op,
            no_op,
            no_op,
            FakeLogger(),
        )
        self.assertEqual(sorted(notifier.actions.keys()), [1, 7, 8])

    def test_global_action_click_dispatches_open_settings_quit(self) -> None:
        tray_module = load_tray_module()
        state = StateController(AppState.IDLE_OK)
        no_op = lambda: None
        fired: list[int] = []
        notifier = tray_module.StatusNotifier(
            state,
            lambda: fired.append(1),
            no_op,
            no_op,
            no_op,
            no_op,
            lambda: fired.append(7),
            lambda: fired.append(8),
            FakeLogger(),
        )
        for item_id in (1, 7, 8):
            notifier._dispatch_click(item_id)
        self.assertEqual(fired, [1, 7, 8])
        for account_item in (100, 200, 210):
            notifier._dispatch_click(account_item)
        self.assertEqual(fired, [1, 7, 8])


if __name__ == "__main__":
    unittest.main()
