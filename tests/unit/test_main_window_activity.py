from __future__ import annotations

import ast
import os
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from nextsync.core.conflict_files import ConflictFile

MAIN_WINDOW = Path(__file__).parents[2] / "src" / "nextsync" / "ui" / "main_window.py"


def method_source(class_name: str, method_name: str) -> str:
    source = MAIN_WINDOW.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for member in node.body:
                if isinstance(member, ast.FunctionDef) and member.name == method_name:
                    return ast.get_source_segment(source, member) or ""
    raise AssertionError(f"{class_name}.{method_name} was not found")


def _has_display() -> bool:
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def _conflict(name: str = "x.txt") -> ConflictFile:
    return ConflictFile(
        path=Path("/tmp/x (Nextcloud conflicted copy 2026-08-01 12:00:00).txt"),
        original_name=name,
        original_path=Path("/tmp/x.txt"),
        conflict_date="2026-08-01 12:00:00",
        size=1,
        modified=0.0,
    )


class StaticRowsContractTests(unittest.TestCase):
    """Issue #30: the log/conflicts rows must not be re-parented on refresh."""

    def test_refresh_activity_does_not_reparent_the_static_rows(self) -> None:
        source = method_source("AccountView", "_refresh_activity")
        self.assertNotIn("self.view_log_row", source)
        self.assertNotIn("self.conflicts_row", source)

    def test_activity_rows_only_holds_activity_rows(self) -> None:
        source = method_source("AccountView", "_refresh_activity")
        self.assertIn("self._activity_rows.extend(rows)", source)
        self.assertNotIn(
            "rows.append(self.view_log_row)", source
        )
        self.assertNotIn(
            "rows.append(self.conflicts_row)", source
        )

    def test_log_row_is_attached_once_outside_the_refresh(self) -> None:
        init_source = method_source("AccountView", "__init__")
        refresh_source = method_source("AccountView", "_refresh_activity")
        self.assertIn("self.activity_expander.add_row(self.view_log_row)", init_source)
        self.assertNotIn("self.activity_expander.add_row(self.view_log_row)", refresh_source)

    def test_conflicts_row_visibility_is_decision_flagged_in_state(self) -> None:
        init_source = method_source("AccountView", "__init__")
        self.assertIn("self._conflicts_scanning = False", init_source)
        self.assertIn("self._conflicts_attached = False", init_source)


class ConflictScanContractTests(unittest.TestCase):
    """Issue #31: conflicts are scanned off the UI thread and the row toggles."""

    def test_conflict_scan_runs_off_the_ui_thread(self) -> None:
        source = method_source("AccountView", "_scan_conflicts")
        self.assertIn("Thread(target=_run, daemon=True).start()", source)
        self.assertIn("GLib.idle_add(self._conflicts_scan_finished, has_conflicts)", source)

    def test_refresh_activity_starts_the_conflict_scan(self) -> None:
        source = method_source("AccountView", "_refresh_activity")
        self.assertIn("self._scan_conflicts()", source)

    def test_should_show_conflicts_is_true_when_find_conflicts_finds_one(self) -> None:
        from nextsync.ui.main_window import AccountView

        with patch(
            "nextsync.ui.main_window.find_conflicts", return_value=[_conflict()]
        ):
            self.assertTrue(
                AccountView._should_show_conflicts(
                    [type("F", (), {"local_root": "/tmp/x"})()]
                )
            )

    def test_should_show_conflicts_is_false_without_conflicts(self) -> None:
        from nextsync.ui.main_window import AccountView

        with patch("nextsync.ui.main_window.find_conflicts", return_value=[]):
            self.assertFalse(
                AccountView._should_show_conflicts(
                    [type("F", (), {"local_root": "/tmp/x"})()]
                )
            )

    def test_should_show_conflicts_is_false_without_folders(self) -> None:
        from nextsync.ui.main_window import AccountView

        with patch("nextsync.ui.main_window.find_conflicts", return_value=[]):
            self.assertFalse(AccountView._should_show_conflicts([]))

    def test_should_show_conflicts_skips_folders_without_local_root(self) -> None:
        from nextsync.ui.main_window import AccountView

        with patch("nextsync.ui.main_window.find_conflicts", return_value=[]):
            self.assertFalse(
                AccountView._should_show_conflicts([type("F", (), {})()])
            )

    def test_should_show_conflicts_returns_early_on_first_match(self) -> None:
        from nextsync.ui.main_window import AccountView

        roots: list[str] = []

        def tracking_find(root: Path):
            roots.append(str(root))
            return [_conflict()] if len(roots) == 1 else []

        with patch(
            "nextsync.ui.main_window.find_conflicts", side_effect=tracking_find
        ):
            self.assertTrue(
                AccountView._should_show_conflicts(
                    [
                        type("F", (), {"local_root": "/tmp/a"})(),
                        type("F", (), {"local_root": "/tmp/b"})(),
                    ]
                )
            )
        self.assertEqual(roots, ["/tmp/a"])


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
                self.scheduler = type(
                    "S",
                    (),
                    {
                        "delete_alert": False,
                        "battery_paused": False,
                        "user_paused": False,
                    },
                )()

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

    def _wait_scan(self, view, glib) -> None:
        deadline = time.time() + 5
        while view._conflicts_scanning and time.time() < deadline:
            self._pump(glib, 2)
            time.sleep(0.01)
        self._pump(glib, 10)

    def test_log_row_survives_two_refreshes_and_still_activates(self) -> None:
        view, glib = self._make_view()
        calls: dict[str, int] = {"show_log": 0}
        view.show_log = lambda *args, **kwargs: calls.__setitem__(
            "show_log", calls["show_log"] + 1
        )
        with patch("nextsync.ui.main_window.find_conflicts", return_value=[]):
            view._refresh_activity()
            view._refresh_activity()
        self.assertIsNotNone(view.view_log_row.get_parent())
        self.assertNotIn(view.view_log_row, view._activity_rows)
        self.assertNotIn(view.conflicts_row, view._activity_rows)
        before = calls["show_log"]
        view.view_log_row.activate()
        self._pump(glib)
        self.assertEqual(calls["show_log"] - before, 1)
        view.dispose()

    def test_conflicts_row_appears_only_when_conflicts_exist(self) -> None:
        view, glib = self._make_view()
        with patch("nextsync.ui.main_window.find_conflicts", return_value=[]):
            view._refresh_activity()
            self._wait_scan(view, glib)
        self.assertIsNone(view.conflicts_row.get_parent())

        with patch(
            "nextsync.ui.main_window.find_conflicts", return_value=[_conflict()]
        ):
            view._refresh_activity()
            self._wait_scan(view, glib)
        self.assertIsNotNone(view.conflicts_row.get_parent())

        with patch("nextsync.ui.main_window.find_conflicts", return_value=[]):
            view._refresh_activity()
            self._wait_scan(view, glib)
        self.assertIsNone(view.conflicts_row.get_parent())
        view.dispose()


if __name__ == "__main__":
    unittest.main()
