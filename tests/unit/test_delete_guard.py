from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pynextcloud_sync.core.delete_guard import (
    DeleteAlert,
    DeleteGuard,
    DeleteGuardManifest,
    find_sync_databases,
    is_sync_database_name,
    scan_local_files,
)
from pynextcloud_sync.core.exclusions import ExclusionMatcher


ACCOUNT = {
    "server_url": "https://cloud.example.com",
    "login_name": "alice",
    "authentication_type": "browser",
    "local_root": "/tmp/NextCloud",
}


def _config(account: dict | None = None, guard: dict | None = None) -> object:
    import types

    data = {
        "account": account or ACCOUNT,
        "sync": {"exclude_patterns": [], "exclude_patterns_enabled": True},
        "delete_guard": guard or {"enabled": True, "count_threshold": 3, "percent_threshold": 20},
    }
    return types.SimpleNamespace(data=data)


class FakeLogger:
    def info(self, *_args: object) -> None:
        pass

    def error(self, *_args: object) -> None:
        pass


class ScanLocalFilesTests(unittest.TestCase):
    def _root(self) -> Path:
        directory = tempfile.mkdtemp(prefix="delete-guard-")
        return Path(directory)

    def test_lists_regular_files_recursively(self) -> None:
        root = self._root()
        (root / "a.txt").write_text("a")
        (root / "sub").mkdir()
        (root / "sub" / "b.bin").write_text("b")
        matcher = ExclusionMatcher([], True)
        files = scan_local_files(root, matcher)
        self.assertEqual(sorted(files), ["a.txt", "sub/b.bin"])

    def test_ignores_journal_and_excluded_names(self) -> None:
        root = self._root()
        (root / ".sync_1.db").write_text("journal")
        (root / "junk.swp").write_text("junk")
        (root / "keep.txt").write_text("k")
        matcher = ExclusionMatcher(["*.swp"], True)
        files = scan_local_files(root, matcher)
        self.assertEqual(files, ["keep.txt"])

    def test_missing_root_is_empty(self) -> None:
        matcher = ExclusionMatcher([], True)
        self.assertEqual(scan_local_files(Path("/nonexistent/guard-root"), matcher), [])

    def test_sync_database_names(self) -> None:
        self.assertTrue(is_sync_database_name(".sync_foo.db"))
        self.assertTrue(is_sync_database_name(".sync.db"))
        self.assertFalse(is_sync_database_name("report.pdf"))
        self.assertFalse(is_sync_database_name(".gitignore"))

    def test_find_sync_databases_returns_top_level_journals(self) -> None:
        root = self._root()
        (root / ".sync_1.db").write_text("j")
        (root / ".sync_2.db").write_text("j")
        (root / "sub").mkdir()
        (root / "sub" / ".sync_3.db").write_text("j")
        found = find_sync_databases(root)
        self.assertEqual(len(found), 2)
        self.assertTrue(all(item.parent == root for item in found))


class DeleteGuardManifestTests(unittest.TestCase):
    def test_paths_differ_per_account(self) -> None:
        a = DeleteGuardManifest.for_account(ACCOUNT)
        other = dict(ACCOUNT)
        other["local_root"] = "/tmp/Other"
        b = DeleteGuardManifest.for_account(other)
        self.assertNotEqual(a.path, b.path)
        self.assertTrue(a.path.name.startswith("delete-guard-"))
        self.assertTrue(a.path.name.endswith(".json"))

    def test_save_and_load_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = DeleteGuardManifest(Path(directory) / "guard.json")
            manifest.save(ACCOUNT, ["a.txt", "b.txt"])
            loaded = manifest.load()
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded["files"], ["a.txt", "b.txt"])

    def test_missing_or_corrupt_manifest_loads_none(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = DeleteGuardManifest(Path(directory) / "guard.json")
            self.assertIsNone(manifest.load())


class DeleteGuardTests(unittest.TestCase):
    def _root_with(self, files: dict[str, str]) -> Path:
        directory = tempfile.mkdtemp(prefix="delete-guard-")
        root = Path(directory)
        for name, content in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        return root

    def _guard(self, root: Path, guard: dict | None = None) -> DeleteGuard:
        account = dict(ACCOUNT)
        account["local_root"] = str(root)
        config = _config(account, guard)
        manifest = DeleteGuardManifest(root.parent / f"guard-{root.name}.json")
        return DeleteGuard(config, FakeLogger(), manifest=manifest)

    def test_no_manifest_means_no_alert(self) -> None:
        root = self._root_with({"a.txt": "a"})
        guard = self._guard(root)
        self.assertIsNone(guard.check())

    def test_mass_deletion_is_blocked(self) -> None:
        root = self._root_with({"a.txt": "a", "b.txt": "b", "c.txt": "c", "d.txt": "d"})
        guard = self._guard(root, {"enabled": True, "count_threshold": 3, "percent_threshold": 60})
        guard.record_current()
        (root / "a.txt").unlink()
        (root / "b.txt").unlink()
        (root / "c.txt").unlink()
        alert = guard.check()
        self.assertIsNotNone(alert)
        assert alert is not None
        self.assertEqual(alert.reason, "mass_local_deletion")
        self.assertGreaterEqual(alert.missing_count, 3)
        self.assertTrue(alert.can_approve_once)

    def test_emptied_folder_is_blocked(self) -> None:
        root = self._root_with({"a.txt": "a"})
        guard = self._guard(root, {"enabled": True, "count_threshold": 3, "percent_threshold": 60})
        guard.record_current()
        (root / "a.txt").unlink()
        alert = guard.check()
        self.assertIsNotNone(alert)
        assert alert is not None
        self.assertEqual(alert.reason, "folder_emptied")
        self.assertTrue(alert.can_approve_once)

    def test_missing_folder_is_blocked_and_not_approvable(self) -> None:
        root = self._root_with({"a.txt": "a"})
        guard = self._guard(root)
        guard.record_current()
        import shutil

        shutil.rmtree(root)
        alert = guard.check()
        self.assertIsNotNone(alert)
        assert alert is not None
        self.assertEqual(alert.reason, "folder_missing")
        self.assertFalse(alert.can_approve_once)

    def test_small_deletion_is_allowed(self) -> None:
        root = self._root_with({"a.txt": "a", "b.txt": "b", "c.txt": "c", "d.txt": "d"})
        guard = self._guard(root, {"enabled": True, "count_threshold": 3, "percent_threshold": 60})
        guard.record_current()
        (root / "a.txt").unlink()
        alert = guard.check()
        self.assertIsNone(alert)

    def test_disabled_guard_never_alerts(self) -> None:
        root = self._root_with({"a.txt": "a"})
        guard = self._guard(root, {"enabled": False, "count_threshold": 3, "percent_threshold": 60})
        guard.record_current()
        (root / "a.txt").unlink()
        self.assertIsNone(guard.check())

    def test_record_current_updates_the_baseline(self) -> None:
        root = self._root_with({"a.txt": "a"})
        guard = self._guard(root, {"enabled": True, "count_threshold": 3, "percent_threshold": 60})
        self.assertTrue(guard.record_current())
        (root / "b.txt").write_text("b")
        self.assertTrue(guard.record_current())
        (root / "a.txt").unlink()
        alert = guard.check()
        self.assertIsNone(alert)


if __name__ == "__main__":
    unittest.main()
