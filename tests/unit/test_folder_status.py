from __future__ import annotations

import os
import unittest
from pathlib import Path

from nextsync.core.account import AccountSession, FolderSession
from nextsync.core.state import AppState, StateController
from nextsync.ui.folder_status import (
    FolderStatusRow,
    folder_status_presentation,
    pair_folder_runtimes,
)


def _folder(folder_id: str, local_root: str = "/tmp/folder") -> FolderSession:
    return FolderSession(folder_id=folder_id, local_root=local_root, remote_path="")


def _has_display() -> bool:
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


class FolderStatusPresentationTests(unittest.TestCase):
    def test_presentation_covers_every_app_state(self) -> None:
        for state in AppState:
            icon, label = folder_status_presentation(state)
            self.assertTrue(icon)
            self.assertTrue(label)

    def test_presentation_labels_are_localized(self) -> None:
        icon, label = folder_status_presentation(AppState.IDLE_OK)
        self.assertEqual(icon, "emblem-ok-symbolic")
        self.assertIn("Synchron", label)


class PairFolderRuntimesTests(unittest.TestCase):
    def test_matches_folders_to_runtimes_by_folder_id(self) -> None:
        first = _folder("f1")
        second = _folder("f2")
        runtimes = {"f1": object(), "f2": object()}
        pairs = pair_folder_runtimes([first, second], runtimes)
        self.assertEqual(pairs[0][0], first)
        self.assertIs(pairs[0][1], runtimes["f1"])
        self.assertEqual(pairs[1][0], second)
        self.assertIs(pairs[1][1], runtimes["f2"])

    def test_unknown_folder_runtime_degrades_to_none(self) -> None:
        folder = _folder("orphan")
        pairs = pair_folder_runtimes([folder], {"other": object()})
        self.assertEqual(pairs[0][0], folder)
        self.assertIsNone(pairs[0][1])

    def test_preserves_session_order(self) -> None:
        folders = [_folder("b"), _folder("a"), _folder("c")]
        runtimes = {"a": object(), "b": object(), "c": object()}
        pairs = pair_folder_runtimes(folders, runtimes)
        self.assertEqual([folder.folder_id for folder, _ in pairs], ["b", "a", "c"])


@unittest.skipUnless(_has_display(), "GTK widgets require a display")
class FolderStatusRowTests(unittest.TestCase):
    def test_subscribes_to_the_state_controller_and_renders(self) -> None:
        controller = StateController(AppState.IDLE_OK)
        row = FolderStatusRow(
            _folder("f1", "/tmp/MyCloud"),
            controller,
            on_open=lambda: None,
            format_last_sync=lambda: "2025-01-01 10:00",
        )
        self.assertEqual(len(controller._listeners), 1)
        self.assertEqual(row.get_title(), "MyCloud")
        self.assertIn("Synchronized", row.get_subtitle())

    def test_remote_path_is_shown_when_present(self) -> None:
        controller = StateController(AppState.IDLE_OK)
        folder = FolderSession(
            folder_id="f1", local_root="/tmp/MyCloud", remote_path="/photos"
        )
        row = FolderStatusRow(
            folder,
            controller,
            on_open=lambda: None,
            format_last_sync=lambda: "",
        )
        self.assertIn("/photos", row.get_subtitle())

    def test_live_state_updates_subtitle_and_spinner(self) -> None:
        controller = StateController(AppState.IDLE_OK)
        row = FolderStatusRow(
            _folder("f1"),
            controller,
            on_open=lambda: None,
            format_last_sync=lambda: "",
        )
        controller.set(AppState.SYNCING, "Uploading files…")
        self.assertIn("Synchronizing", row.get_subtitle())
        self.assertTrue(row._spinner.get_visible())
        controller.set(AppState.ERROR, "Synchronization failed")
        self.assertFalse(row._spinner.get_visible())
        self.assertEqual(row.get_subtitle(), "Synchronization Error")

    def test_dispose_unsubscribes_from_the_state_controller(self) -> None:
        controller = StateController(AppState.IDLE_OK)
        row = FolderStatusRow(
            _folder("f1"),
            controller,
            on_open=lambda: None,
            format_last_sync=lambda: "",
        )
        row.dispose()
        self.assertEqual(len(controller._listeners), 0)

    def test_without_runtime_renders_unconfigured(self) -> None:
        row = FolderStatusRow(
            _folder("f1"),
            None,
            on_open=lambda: None,
            format_last_sync=lambda: "",
        )
        self.assertEqual(row.get_title(), "folder")
        self.assertIn("Not Configured", row.get_subtitle())


@unittest.skipUnless(_has_display(), "GTK widgets require a display")
class AccountViewFolderRowTests(unittest.TestCase):
    def test_zero_folders_shows_the_informative_row(self) -> None:
        session = AccountSession(
            account_id="a1",
            server_url="https://cloud.example.com",
            login_name="alice",
            authentication_type="manual",
            folders=[],
        )
        runtime = _FakeAccountRuntime(folders={})
        logger = _FakeLogger()
        from nextsync.ui.main_window import AccountView

        view = AccountView(None, None, session, runtime, logger)
        titles = _row_titles(view.account_list)
        self.assertIn("No Synchronization Folders", titles)
        self.assertNotIn("Last Successful Sync", titles[:-1])

    def test_one_folder_shows_a_folder_status_row(self) -> None:
        folder = FolderSession(
            folder_id="f1",
            local_root="/tmp/MyCloud",
            remote_path="/photos",
        )
        session = AccountSession(
            account_id="a1",
            server_url="https://cloud.example.com",
            login_name="alice",
            authentication_type="manual",
            folders=[folder],
        )
        runtime = _FakeAccountRuntime(
            folders={"f1": _FakeFolderRuntime(folder, AppState.IDLE_OK)}
        )
        from nextsync.ui.main_window import AccountView

        view = AccountView(None, None, session, runtime, _FakeLogger())
        titles = _row_titles(view.account_list)
        self.assertIn("MyCloud", titles)
        subtitles = _row_subtitles(view.account_list)
        self.assertTrue(
            any("Synchronized" in subtitle for subtitle in subtitles),
            subtitles,
        )
        view.dispose()


def _row_titles(listbox: object) -> list[str]:
    titles = []
    child = listbox.get_first_child()
    while child is not None:
        target = child if hasattr(child, "get_title") else child.get_child()
        if hasattr(target, "get_title"):
            titles.append(target.get_title())
        child = child.get_next_sibling()
    return titles


def _row_subtitles(listbox: object) -> list[str]:
    subtitles = []
    child = listbox.get_first_child()
    while child is not None:
        target = child if hasattr(child, "get_title") else child.get_child()
        if hasattr(target, "get_subtitle"):
            subtitles.append(target.get_subtitle())
        child = child.get_next_sibling()
    return subtitles


class _FakeAccountRuntime:
    def __init__(self, folders: dict[str, object]) -> None:
        self.folders = folders
        self.state = StateController(AppState.IDLE_OK)

    def set_paused(self, paused: bool) -> None:
        pass


class _FakeFolderRuntime:
    def __init__(self, folder: FolderSession, state: AppState) -> None:
        self.folder = folder
        self.state = StateController(state)
        self.session = AccountSession(
            account_id="a1",
            server_url="https://cloud.example.com",
            login_name="alice",
            authentication_type="manual",
            folders=[folder],
        )


class _FakeLogger:
    def recent_lines(self, limit: int) -> list[str]:
        return []

    def subscribe(self, callback: object) -> object:
        return lambda: None


if __name__ == "__main__":
    unittest.main()
