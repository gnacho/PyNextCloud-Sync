from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from nextsync.core.conflict_files import (
    CONFLICT_RE,
    find_conflicts,
    keep_local,
    keep_remote,
)


class ConflictPatternTests(unittest.TestCase):
    def test_matches_engine_pattern(self) -> None:
        match = CONFLICT_RE.match(
            "report.pdf (Nextcloud conflicted copy 2026-08-11 23-45-12).pdf"
        )
        self.assertIsNotNone(match)
        assert match is not None
        self.assertEqual(match.group("stem"), "report.pdf")
        self.assertEqual(match.group("extension"), ".pdf")
        self.assertEqual(match.group("date"), "2026-08-11 23-45-12")

    def test_matches_date_only(self) -> None:
        match = CONFLICT_RE.match("notes (Nextcloud conflicted copy 2026-08-11).txt")
        self.assertIsNotNone(match)
        assert match is not None
        self.assertEqual(match.group("stem"), "notes")
        self.assertEqual(match.group("date"), "2026-08-11")

    def test_does_not_match_plain_files(self) -> None:
        for name in ("report.pdf", "conflicted copy.txt", "Nextcloud conflicted"):
            self.assertIsNone(CONFLICT_RE.match(name), name)


class FindConflictsTests(unittest.TestCase):
    def _root(self) -> Path:
        directory = tempfile.mkdtemp(prefix="conflict-test-")
        return Path(directory)

    def test_finds_only_conflicted_copies(self) -> None:
        root = self._root()
        (root / "normal.txt").write_text("a")
        (root / "report.pdf (Nextcloud conflicted copy 2026-08-11 09-30-00).pdf").write_text("b")
        (root / "docs").mkdir()
        (root / "docs" / "note (Nextcloud conflicted copy 2026-08-10).md").write_text("c")
        conflicts = find_conflicts(root)
        names = [item.name for item in conflicts]
        self.assertEqual(len(names), 2)
        self.assertIn("report.pdf (Nextcloud conflicted copy 2026-08-11 09-30-00).pdf", names)
        self.assertIn("note (Nextcloud conflicted copy 2026-08-10).md", names)

    def test_original_path_is_derived(self) -> None:
        root = self._root()
        name = "report.pdf (Nextcloud conflicted copy 2026-08-11 09-30-00).pdf"
        (root / name).write_text("b")
        conflicts = find_conflicts(root)
        self.assertEqual(len(conflicts), 1)
        conflict = conflicts[0]
        self.assertEqual(conflict.original_name, "report.pdf")
        self.assertEqual(conflict.original_path, root / "report.pdf")

    def test_empty_root_yields_no_conflicts(self) -> None:
        self.assertEqual(find_conflicts(self._root()), [])

    def test_missing_root_yields_no_conflicts(self) -> None:
        self.assertEqual(find_conflicts(Path("/nonexistent/conflict-root")), [])

    def test_keep_local_deletes_the_copy(self) -> None:
        root = self._root()
        name = "report.pdf (Nextcloud conflicted copy 2026-08-11 09-30-00).pdf"
        path = root / name
        path.write_text("b")
        original = root / "report.pdf"
        original.write_text("keep-me")
        conflicts = find_conflicts(root)
        self.assertTrue(keep_local(conflicts[0]))
        self.assertFalse(path.exists())
        self.assertTrue(original.exists())
        self.assertEqual(original.read_text(), "keep-me")

    def test_keep_remote_replaces_the_working_file(self) -> None:
        root = self._root()
        name = "report.pdf (Nextcloud conflicted copy 2026-08-11 09-30-00).pdf"
        (root / name).write_text("remote-content")
        original = root / "report.pdf"
        original.write_text("local-content")
        conflicts = find_conflicts(root)
        self.assertTrue(keep_remote(conflicts[0]))
        self.assertTrue(original.exists())
        self.assertEqual(original.read_text(), "remote-content")

    def test_progress_callback_reports_counts(self) -> None:
        root = self._root()
        (root / "a (Nextcloud conflicted copy 2026-08-11).txt").write_text("x")
        (root / "b.txt").write_text("y")
        calls: list[tuple[int, int]] = []

        def progress(current: int, total: int) -> None:
            calls.append((current, total))

        find_conflicts(root, progress=progress)
        self.assertEqual(calls, [(1, 2), (2, 2)])


if __name__ == "__main__":
    unittest.main()
