from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nextsync.core.account import AccountSession
from nextsync.core.account_manager import (
    AccountManager,
    AccountRuntime,
    FolderConfigView,
)
from nextsync.core.state import AppState, StateController
from nextsync.storage.config import (
    ConfigStore,
    validate_config,
)


def _config_with(accounts: list[dict]) -> object:
    data = validate_config({"schema_version": 6, "accounts": accounts})
    return type("Config", (), {"data": data, "accounts": accounts})()

def _store_with(accounts: list[dict]) -> ConfigStore:
    store = ConfigStore(Path("/tmp/unused-settings.json"))
    store.data = validate_config({"schema_version": 6, "accounts": accounts})
    return store


ACCOUNT_A = {
    "server_url": "https://cloud.example.com",
    "login_name": "alice",
    "authentication_type": "browser",
    "folders": [{"local_root": "/tmp/NextCloud"}],
}
ACCOUNT_B = {
    "server_url": "https://work.example.com",
    "login_name": "bob",
    "authentication_type": "manual",
    "folders": [{"local_root": "/tmp/WorkCloud"}],
}


class FolderConfigViewTests(unittest.TestCase):
    def test_view_serves_the_session_account_settings(self) -> None:
        config = _store_with([ACCOUNT_A])
        session = AccountSession.from_config_value(config.data["accounts"][0])
        view = FolderConfigView(config, session)
        self.assertEqual(view.data["account"]["login_name"], "alice")
        self.assertEqual(view.data["account"]["local_root"], "/tmp/NextCloud")
        self.assertEqual(view.data["sync"], session.sync)

    def test_view_forwards_global_sections_from_the_store(self) -> None:
        config = _store_with([ACCOUNT_A])
        session = AccountSession.from_config_value(config.data["accounts"][0])
        view = FolderConfigView(config, session)
        self.assertIs(view.data["network"], config.data["network"])
        self.assertIs(view.data["general"], config.data["general"])

    def test_view_serves_an_empty_account_when_no_folder_is_configured(self) -> None:
        store = _store_with([{**ACCOUNT_A, "folders": []}])
        session = AccountSession.from_config_value(store.data["accounts"][0])
        view = FolderConfigView(store, session)
        self.assertEqual(view.data["account"]["local_root"], "")

    def test_save_writes_session_settings_back_to_the_store(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(Path(directory) / "settings.json")
            store.data = validate_config(
                {"schema_version": 6, "accounts": [copy.deepcopy(ACCOUNT_A)]}
            )
            session = AccountSession.from_config_value(store.data["accounts"][0])
            view = FolderConfigView(store, session)
            session.sync["max_sync_retries"] = 7
            view.save(notify=False)
            self.assertEqual(
                store.data["accounts"][0]["sync"]["max_sync_retries"], 7
            )

    def test_subscribe_and_unsubscribe(self) -> None:
        config = _store_with([ACCOUNT_A])
        session = AccountSession.from_config_value(config.data["accounts"][0])
        view = FolderConfigView(config, session)
        seen: list[dict] = []
        unsubscribe = view.subscribe(lambda data: seen.append(data))
        view.save()
        self.assertEqual(len(seen), 1)
        unsubscribe()
        view.save()
        self.assertEqual(len(seen), 1)


class FakeRuntimeController:
    def __init__(self, *args: object, **kwargs: object) -> None:
        self.started = False
        self.stopped = False
        self.state = StateController(AppState.IDLE_OK)

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True


class AccountManagerTests(unittest.TestCase):
    def test_manager_starts_one_runtime_per_account_and_folder(self) -> None:
        store = _store_with(
            [
                {**ACCOUNT_A, "folders": [{"local_root": "/tmp/NextCloud"}, {"local_root": "/tmp/NextCloud2"}]},
                ACCOUNT_B,
            ]
        )
        with patch(
            "nextsync.core.account_manager.RuntimeController",
            FakeRuntimeController,
        ):
            manager = AccountManager(store, None, None)
            manager.start()
            self.assertEqual(len(manager.runtimes), 2)
            self.assertTrue(all(r.folders for r in manager.runtimes.values()))
            self.assertTrue(
                all(
                    folder_runtime.runtime.started
                    for r in manager.runtimes.values()
                    for folder_runtime in r.folders.values()
                )
            )

    def test_account_without_folders_has_no_folder_runtimes(self) -> None:
        store = _store_with([{**ACCOUNT_A, "folders": []}])
        with patch(
            "nextsync.core.account_manager.RuntimeController",
            FakeRuntimeController,
        ):
            manager = AccountManager(store, None, None)
            manager.start()
            self.assertEqual(len(manager.runtimes), 1)
            self.assertEqual(list(manager.runtimes.values())[0].folders, {})

    def test_manager_stop_stops_all_runtimes(self) -> None:
        store = _store_with([ACCOUNT_A])
        with patch(
            "nextsync.core.account_manager.RuntimeController",
            FakeRuntimeController,
        ):
            manager = AccountManager(store, None, None)
            manager.start()
            manager.stop()
            self.assertEqual(manager.runtimes, {})

    def test_remove_drops_one_runtime_and_keeps_the_rest(self) -> None:
        store = _store_with([ACCOUNT_A, ACCOUNT_B])
        with patch(
            "nextsync.core.account_manager.RuntimeController",
            FakeRuntimeController,
        ):
            manager = AccountManager(store, None, None)
            manager.start()
            kept_id, dropped_id = tuple(manager.runtimes)
            removed = manager.remove(dropped_id)
            self.assertTrue(removed)
            self.assertNotIn(dropped_id, manager.runtimes)
            self.assertIn(kept_id, manager.runtimes)
            dropped = manager.runtimes[dropped_id] if dropped_id in manager.runtimes else None
            self.assertIsNone(dropped)
            self.assertFalse(manager.remove("nonexistent"))


if __name__ == "__main__":
    unittest.main()
