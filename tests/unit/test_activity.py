from __future__ import annotations

import unittest
from pathlib import Path

from nextsync.ui.activity import parse_activity_line


class ActivityTests(unittest.TestCase):
    def test_parses_level_without_exposing_prefix_in_message(self) -> None:
        entry = parse_activity_line(
            "2026-08-07 14:12:41 INFO    Synchronization completed successfully."
        )
        self.assertEqual(entry.level, "INFO")
        self.assertEqual(entry.message, "Synchronization completed successfully.")
        self.assertEqual(entry.icon_name, "emblem-ok-symbolic")

    def test_preserves_literal_ampersand_from_nextcloudcmd(self) -> None:
        entry = parse_activity_line(
            "2026-08-07 14:12:41 INFO    CMD lambda(const QJsonDocument&)"
        )
        self.assertIn("QJsonDocument&", entry.message)

    def test_warning_has_warning_icon(self) -> None:
        entry = parse_activity_line("2026-08-07 14:12:41 WARNING Push unavailable")
        self.assertEqual(entry.level, "WARNING")
        self.assertEqual(entry.icon_name, "dialog-warning-symbolic")

    def test_main_window_no_longer_renders_activity_rows(self) -> None:
        # Issue #34: the account view focuses on synchronized folders; recent
        # activity, log and conflicts rows were removed from the account view.
        source = (
            Path(__file__).parents[2]
            / "src"
            / "nextsync"
            / "ui"
            / "main_window.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("_activity_row", source)
        self.assertNotIn('_("Copy Message")', source)
        self.assertNotIn("self.activity_expander", source)


if __name__ == "__main__":
    unittest.main()
