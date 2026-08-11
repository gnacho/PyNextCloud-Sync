from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pynextcloud_sync.core.account import AccountSession
from pynextcloud_sync.core.account_manager import (
    AccountConfigView,
    AccountManager,
    AccountRuntime,
)
from pynextcloud_sync.core.state import AppState, StateController
from pynextcloud_sync.core.safety import SafetyManifest
from pynextcloud_sync.core.sync_run_marker import SyncRunMarker
from pynextcloud_sync.storage.config import (
    DEFAULT_CONFIG,
    ConfigStore,
    validate_config,
)


def _config_with(accounts: list[dict]) -> object:
    data = validate_config({"schema_version": 3, "accounts": accounts})
    return type("Config", (), {"data": data, "accounts": accounts})()

def _store_with(accounts: list[dict]) -> ConfigStore:
    store = ConfigStore(Path("/tmp/unused-settings.json"))
    store.data = validate_config({"schema_version": 3, "accounts": accounts})
    return store


ACCOUNT_A = {
    "server_url": "https://cloud.example.com",
    "login_name": "alice",
    "authentication_type": "browser",
    "local_root": "/tmp/NextCloud",
    "safety": {"bootstrap_complete": True},
}
ACCOUNT_B = {
    "server_url": "https://work.example.com",
    "login_name": "bob",
    "authentication_type": "manual",
    "local_root": "/tmp/WorkCloud",
    "safety": {"bootstrap_complete": True},
}


class ManifestPerAccountTests(unittest.TestCase):
    def test_manifest_paths_differ_per_account(self) -> None:
        a = SafetyManifest.for_account(ACCOUNT_A)
        b = SafetyManifest.for_account(ACCOUNT_B)
        self.assertNotEqual(a.path, b.path)
        self.assertTrue(a.path.name.startswith("safety-manifest-"))
        self.assertTrue(a.path.name.endswith(".json"))

    def test_run_marker_paths_differ_per_account(self) -> None:
        a = SyncRunMarker.for_account(ACCOUNT_A)
        b = SyncRunMarker.for_account(ACCOUNT_B)
        self.assertNotEqual(a.path, b.path)
        self.assertTrue(a.path.name.startswith("sync-run-"))
        self.assertTrue(a.path.name.endswith(".json"))


class AccountConfigViewTests(unittest.TestCase):
    def test_view_serves_the_session_account_settings(self) -> None:
        config = _store_with([ACCOUNT_A])
        session = AccountSession.from_config_value(config.data["accounts"][0])
        view = AccountConfigView(config, session)
        self.assertEqual(view.data["account"]["login_name"], "alice")
        self.assertEqual(view.data["sync"], session.sync)
        self.assertEqual(view.data["safety"], session.safety)

    def test_view_forwards_global_sections_from_the_store(self) -> None:
        config = _store_with([ACCOUNT_A])
        session = AccountSession.from_config_value(config.data["accounts"][0])
        view = AccountConfigView(config, session)
        self.assertIs(view.data["network"], config.data["network"])
        self.assertIs(view.data["general"], config.data["general"])

    def test_save_writes_session_settings_back_to_the_store(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(Path(directory) / "settings.json")
            store.data = validate_config(
                {"schema_version": 3, "accounts": [copy.deepcopy(ACCOUNT_A)]}
            )
            session = AccountSession.from_config_value(store.data["accounts"][0])
            view = AccountConfigView(store, session)
            session.sync["max_sync_retries"] = 7
            view.save(notify=False)
            self.assertEqual(
                store.data["accounts"][0]["sync"]["max_sync_retries"], 7
            )

    def test_subscribe_and_unsubscribe(self) -> None:
        config = _store_with([ACCOUNT_A])
        session = AccountSession.from_config_value(config.data["accounts"][0])
        view = AccountConfigView(config, session)
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
    def test_manager_starts_one_runtime_per_account(self) -> None:
        store = _store_with([ACCOUNT_A, ACCOUNT_B])
        with patch(
            "pynextcloud_sync.core.account_manager.RuntimeController",
            FakeRuntimeController,
        ):
            manager = AccountManager(store, None, None)
            manager.start()
            self.assertEqual(len(manager.runtimes), 2)
            self.assertTrue(all(r.runtime.started for r in manager.runtimes.values()))

    def test_manager_stop_stops_all_runtimes(self) -> None:
        store = _store_with([ACCOUNT_A])
        with patch(
            "pynextcloud_sync.core.account_manager.RuntimeController",
            FakeRuntimeController,
        ):
            manager = AccountManager(store, None, None)
            manager.start()
            manager.stop()
            self.assertEqual(manager.runtimes, {})

    def test_remove_drops_one_runtime_and_keeps_the_rest(self) -> None:
        store = _store_with([ACCOUNT_A, ACCOUNT_B])
        with patch(
            "pynextcloud_sync.core.account_manager.RuntimeController",
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
