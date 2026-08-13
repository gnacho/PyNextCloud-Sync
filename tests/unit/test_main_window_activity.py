from __future__ import annotations

import ast
import os
import unittest
from pathlib import Path

MAIN_WINDOW = Path(__file__).parents[2] / "src" / "nextsync" / "ui" / "main_window.py"
FOLDER_STATUS = (
    Path(__file__).parents[2] / "src" / "nextsync" / "ui" / "folder_status.py"
)


def file_source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def method_source(class_name: str, method_name: str, path: Path = MAIN_WINDOW) -> str:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for member in node.body:
                if isinstance(member, ast.FunctionDef) and member.name == method_name:
                    return ast.get_source_segment(source, member) or ""
    raise AssertionError(f"{class_name}.{method_name} was not found")


def _has_display() -> bool:
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


class AccountViewFocusContractTests(unittest.TestCase):
    """Issue #34: the account view focuses on synchronized folders."""

    def test_account_view_has_no_activity_expander(self) -> None:
        source = method_source("AccountView", "__init__")
        self.assertNotIn("activity_expander", source)
        self.assertNotIn("Recent Activity", source)

    def test_account_view_has_no_log_or_conflicts_rows(self) -> None:
        source = method_source("AccountView", "__init__")
        self.assertNotIn("view_log_row", source)
        self.assertNotIn("conflicts_row", source)

    def test_account_view_has_no_activity_or_conflict_scanning(self) -> None:
        full = file_source(MAIN_WINDOW)
        self.assertNotIn("def _refresh_activity", full)
        self.assertNotIn("def _scan_conflicts", full)
        self.assertNotIn("def _should_show_conflicts", full)
        self.assertNotIn("_activity_rows", full)

    def test_account_view_keeps_only_folder_list_and_buttons(self) -> None:
        source = method_source("AccountView", "__init__")
        self.assertIn("FolderStatusRow(", source)
        self.assertIn("self.sync_button", source)
        self.assertIn("self.pause_button", source)
        self.assertNotIn("self.last_row", source)
        self.assertNotIn('avatar-default-symbolic"', source)

    def test_every_folder_row_wires_the_folder_menu_actions(self) -> None:
        source = method_source("AccountView", "__init__")
        for fragment in (
            "on_edit_ignored",
            "on_force_sync",
            "on_toggle_pause",
            "on_remove",
            "is_paused",
        ):
            self.assertIn(fragment, source)


class FolderMenuContractTests(unittest.TestCase):
    """Issue #34: the folder row exposes the per-folder actions."""

    def test_folder_row_has_a_more_menu_button(self) -> None:
        source = method_source(
            "FolderStatusRow", "__init__", path=FOLDER_STATUS
        )
        self.assertIn("Gtk.MenuButton(", source)
        self.assertIn("view-more-symbolic", source)

    def test_menu_builds_open_edit_force_pause_remove_items(self) -> None:
        source = method_source(
            "FolderStatusRow", "_rebuild_menu", path=FOLDER_STATUS
        )
        for fragment in (
            'Open local folder"',
            'Edit ignored files"',
            'Force sync now"',
            "Pause sync",
            "Remove synchronization",
        ):
            self.assertIn(fragment, source)

    def test_actions_are_registered_once_in_the_constructor(self) -> None:
        source = method_source(
            "FolderStatusRow", "__init__", path=FOLDER_STATUS
        )
        self.assertIn('self._actions: dict[str, Gio.SimpleAction] = {}', source)


@unittest.skipUnless(_has_display(), "requires a GTK display")
class AccountViewDisplayTests(unittest.TestCase):
    """Functional checks that need a real GTK display."""

    def _make_view(self):
        import gi

        gi.require_version("Gtk", "4.0")
        from gi.repository import Gtk, GLib

        from nextsync.core.account import AccountSession, FolderSession
        from nextsync.core.state import StateController
        from nextsync.ui.main_window import AccountView

        session = AccountSession(
            account_id="a",
            server_url="https://example.com",
            login_name="user",
            authentication_type="manual",
            folders=[FolderSession(folder_id="f", local_root="/tmp/nxs-test-root")],
        )

        class FakeLogger:
            def recent_lines(self, _n: int):
                return []

            def subscribe(self, _cb):
                return lambda: None

        class FakeRuntime:
            def __init__(self) -> None:
                self.state = StateController()
                self.folders = {}
                self.scheduler = type(
                    "S",
                    (),
                    {
                        "delete_alert": False,
                        "battery_paused": False,
                        "user_paused": False,
                    },
                )()

            def set_paused(self, paused: bool) -> None:
                pass

            def sync_now(self) -> None:
                pass

        view = AccountView(
            application=None,
            config=type("C", (), {"accounts": []})(),
            session=session,
            runtime=FakeRuntime(),
            logger=FakeLogger(),
        )
        window = Gtk.Window()
        window.set_child(view)
        window.present()
        self.addCleanup(window.destroy)
        return view, GLib

    def _pump(self, glib, rounds: int = 8) -> None:
        for _ in range(rounds):
            while glib.MainContext.default().pending():
                glib.MainContext.default().iteration(False)

    def test_folder_rows_render_one_row_per_folder(self) -> None:
        view, glib = self._make_view()
        folder_rows = 0
        child = view.account_list.get_first_child()
        while child is not None:
            target = (
                child
                if hasattr(child, "_menu_button")
                else (child.get_child() if hasattr(child, "get_child") else child)
            )
            if hasattr(target, "_menu_button"):
                folder_rows += 1
            child = child.get_next_sibling()
        self.assertEqual(folder_rows, 1)
        view.dispose()

    def test_remove_folder_dialog_can_be_opened(self) -> None:
        view, glib = self._make_view()
        target = None
        child = view.account_list.get_first_child()
        while child is not None:
            cand = (
                child
                if hasattr(child, "_menu_button")
                else (child.get_child() if hasattr(child, "get_child") else child)
            )
            if hasattr(cand, "_menu_button"):
                target = cand
                break
            child = child.get_next_sibling()
        self.assertIsNotNone(target)
        self.assertIsNotNone(target._menu_button)
        view.dispose()


if __name__ == "__main__":
    unittest.main()
