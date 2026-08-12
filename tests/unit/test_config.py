from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from nextsync.storage.config import (
    DEFAULT_CONFIG,
    ConfigStore,
    ConfigurationError,
    account_id,
    folder_fingerprint,
    normalize_remote_path,
    normalize_server_url,
    validate_config,
)


ACCOUNT = {
    "server_url": "https://cloud.example.com",
    "login_name": "alice",
    "authentication_type": "browser",
    "folders": [{"local_root": "/tmp/NextCloud"}],
}


class ConfigTests(unittest.TestCase):
    def test_normalizes_server_url(self) -> None:
        self.assertEqual(
            normalize_server_url(" HTTPS://cloud.example.com/nextcloud/ "),
            "https://cloud.example.com/nextcloud",
        )

    def test_rejects_credentials_in_url(self) -> None:
        with self.assertRaises(ConfigurationError):
            normalize_server_url("https://user:secret@cloud.example.com")

    def test_unknown_newer_schema_is_not_discarded(self) -> None:
        data = copy.deepcopy(DEFAULT_CONFIG)
        data["schema_version"] = 999
        with self.assertRaises(ConfigurationError):
            validate_config(data)

    def test_rejects_proxy_credentials(self) -> None:
        data = copy.deepcopy(DEFAULT_CONFIG)
        data["network"]["custom_proxy"] = "http://user:secret@proxy.example.com:8080"
        with self.assertRaises(ConfigurationError):
            validate_config(data)

    def test_logging_defaults_are_merged_into_existing_configuration(self) -> None:
        validated = validate_config({"schema_version": 1})
        self.assertTrue(validated["logging"]["save_logs"])
        self.assertEqual(validated["logging"]["retention_days"], 30)
        self.assertEqual(validated["accounts"], [])
        self.assertNotIn("safety", validated)

    def test_legacy_safety_fields_are_dropped(self) -> None:
        account = dict(ACCOUNT)
        account["safety"] = {
            "bootstrap_complete": True,
            "guard_enabled": True,
            "deletion_count_threshold": 10,
        }
        account["bootstrap_complete"] = False
        data = copy.deepcopy(DEFAULT_CONFIG)
        data["schema_version"] = 4
        data["accounts"] = [account]
        validated = validate_config(data)
        self.assertEqual(validated["schema_version"], 6)
        self.assertNotIn("safety", validated["accounts"][0])
        self.assertNotIn("bootstrap_complete", validated["accounts"][0])

    def test_rejects_invalid_log_retention(self) -> None:
        data = copy.deepcopy(DEFAULT_CONFIG)
        data["logging"]["retention_days"] = 0
        with self.assertRaises(ConfigurationError):
            validate_config(data)

    def test_atomic_store_contains_no_secret_field(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            store = ConfigStore(path)
            store.data = copy.deepcopy(DEFAULT_CONFIG)
            store.add_account(dict(ACCOUNT))
            raw = path.read_text(encoding="utf-8")
            self.assertNotIn("appPassword", raw)
            self.assertNotIn('"password"', raw.lower())
            self.assertEqual(json.loads(raw)["accounts"][0]["login_name"], "alice")

    def test_legacy_single_account_migrates_to_accounts_list(self) -> None:
        legacy = {
            "schema_version": 2,
            "account": {
                "server_url": "https://cloud.example.com",
                "login_name": "alice",
                "authentication_type": "browser",
                "local_root": "/tmp/NextCloud",
            },
            "sync": {"local_interval_minutes": 7},
            "safety": {"bootstrap_complete": True},
            "runtime": {"last_exit_code": 3},
            "general": {"autostart": False},
        }
        validated = validate_config(legacy)
        self.assertEqual(len(validated["accounts"]), 1)
        migrated = validated["accounts"][0]
        self.assertEqual(migrated["login_name"], "alice")
        self.assertEqual(migrated["sync"]["local_interval_minutes"], 7)
        self.assertNotIn("safety", migrated)
        self.assertNotIn("bootstrap_complete", migrated)
        self.assertEqual(migrated["runtime"]["last_exit_code"], 3)
        self.assertFalse(validated["general"]["autostart"])
        self.assertEqual(len(migrated["folders"]), 1)
        self.assertEqual(migrated["folders"][0]["local_root"], "/tmp/NextCloud")

    def test_legacy_view_aliases_the_first_account(self) -> None:
        validated = validate_config(
            {
                "schema_version": 2,
                "account": {
                    "server_url": "https://cloud.example.com",
                    "login_name": "alice",
                    "authentication_type": "browser",
                    "local_root": "/tmp/NextCloud",
                },
                "sync": {"max_sync_retries": 9},
            }
        )
        self.assertEqual(validated["account"]["login_name"], "alice")
        self.assertEqual(validated["sync"]["max_sync_retries"], 9)
        self.assertIs(validated["sync"], validated["accounts"][0]["sync"])

    def test_multiple_accounts_keep_independent_settings(self) -> None:
        first = dict(ACCOUNT)
        second = {
            "server_url": "https://work.example.com",
            "login_name": "bob",
            "authentication_type": "manual",
            "folders": [{"local_root": "/tmp/WorkCloud"}],
            "sync": {"remote_interval_minutes": 55},
        }
        validated = validate_config({"schema_version": 6, "accounts": [first, second]})
        self.assertEqual(len(validated["accounts"]), 2)
        self.assertEqual(validated["accounts"][1]["sync"]["remote_interval_minutes"], 55)
        self.assertEqual(validated["accounts"][0]["sync"]["remote_interval_minutes"], 10)
        self.assertNotEqual(
            validated["accounts"][0]["id"], validated["accounts"][1]["id"]
        )

    def test_add_and_remove_account_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            store = ConfigStore(path)
            store.load()
            store.add_account(dict(ACCOUNT))
            second = {
                "server_url": "https://work.example.com",
                "login_name": "bob",
                "authentication_type": "manual",
                "folders": [{"local_root": "/tmp/WorkCloud"}],
            }
            account_id = store.add_account(second)
            self.assertTrue(store.configured)
            self.assertEqual(len(store.accounts), 2)
            self.assertTrue(store.remove_account(account_id))
            self.assertEqual(len(store.accounts), 1)
            self.assertEqual(store.accounts[0]["login_name"], "alice")
            reloaded = ConfigStore(path)
            reloaded.load()
            self.assertEqual(len(reloaded.accounts), 1)
            self.assertEqual(reloaded.accounts[0]["login_name"], "alice")

    def test_add_duplicate_account_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(Path(directory) / "settings.json")
            store.add_account(dict(ACCOUNT))
            with self.assertRaises(ConfigurationError):
                store.add_account(dict(ACCOUNT))

    def test_reset_account_clears_everything(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(Path(directory) / "settings.json")
            store.add_account(dict(ACCOUNT))
            store.reset_account()
            self.assertFalse(store.configured)
            self.assertEqual(store.accounts, [])

    def test_account_id_is_stable_and_ignores_folders(self) -> None:
        first = account_id("https://cloud.example.com", "alice")
        self.assertEqual(first, account_id("https://cloud.example.com", "alice"))
        other = account_id("https://cloud.example.com", "bob")
        self.assertNotEqual(first, other)
        self.assertEqual(
            first, account_id("HTTPS://cloud.example.com/", "ALICE")
        )

    def test_folder_fingerprint_depends_on_the_folder_pair(self) -> None:
        base = folder_fingerprint("https://cloud.example.com", "alice", "/tmp/NextCloud", "")
        self.assertEqual(
            base,
            folder_fingerprint("https://cloud.example.com", "alice", "/tmp/NextCloud", ""),
        )
        with_remote = folder_fingerprint(
            "https://cloud.example.com", "alice", "/tmp/NextCloud", "/Documents"
        )
        self.assertNotEqual(base, with_remote)

    def test_remote_path_root_is_empty_after_normalize(self) -> None:
        self.assertEqual(normalize_remote_path(""), "")
        self.assertEqual(normalize_remote_path("/"), "")
        self.assertEqual(normalize_remote_path(None), "")

    def test_remote_path_strips_trailing_slash_and_prepends_leading_slash(self) -> None:
        self.assertEqual(normalize_remote_path("Documents"), "/Documents")
        self.assertEqual(normalize_remote_path("/Documents/"), "/Documents")
        self.assertEqual(normalize_remote_path("/Photos/2026/Summer/"), "/Photos/2026/Summer")

    def test_remote_path_rejects_parent_references_and_query(self) -> None:
        for bad in ("/../etc", "/Documents/../Secrets", "/a?b", "/x#y", "https://host/nc"):
            with self.assertRaises(ConfigurationError):
                normalize_remote_path(bad)

    def test_remote_path_persists_through_validate_config(self) -> None:
        account = dict(ACCOUNT)
        account["folders"][0]["remote_path"] = "/Documents"
        validated = validate_config(
            {"schema_version": 6, "accounts": [account]}
        )
        self.assertEqual(
            validated["accounts"][0]["folders"][0]["remote_path"], "/Documents"
        )
        self.assertEqual(validated["account"]["remote_path"], "/Documents")

    def test_remote_path_defaults_to_root_for_legacy_accounts(self) -> None:
        legacy = {
            "schema_version": 2,
            "account": {
                "server_url": "https://cloud.example.com",
                "login_name": "alice",
                "authentication_type": "browser",
                "local_root": "/tmp/NextCloud",
            },
            "sync": {"max_sync_retries": 9},
        }
        validated = validate_config(legacy)
        self.assertEqual(validated["accounts"][0]["folders"][0]["remote_path"], "")
        self.assertEqual(validated["account"]["remote_path"], "")

    def test_add_folders_to_an_account(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(Path(directory) / "settings.json")
            account_id = store.add_account(dict(ACCOUNT))
            folder_id = store.add_folder(account_id, {"local_root": "/tmp/Second"})
            self.assertEqual(len(store.account(account_id)["folders"]), 2)
            self.assertEqual(store.account(account_id)["folders"][1]["local_root"], "/tmp/Second")
            with self.assertRaises(ConfigurationError):
                store.add_folder(account_id, {"local_root": "/tmp/NextCloud"})
            self.assertTrue(store.remove_folder(account_id, folder_id))
            self.assertEqual(len(store.account(account_id)["folders"]), 1)

    def test_two_accounts_may_share_a_local_folder(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(Path(directory) / "settings.json")
            store.add_account(dict(ACCOUNT))
            other = {
                "server_url": "https://work.example.com",
                "login_name": "bob",
                "authentication_type": "manual",
                "folders": [{"local_root": "/tmp/NextCloud"}],
            }
            store.add_account(other)
            self.assertEqual(len(store.accounts), 2)
            self.assertEqual(
                {a["folders"][0]["local_root"] for a in store.accounts}, {"/tmp/NextCloud"}
            )


if __name__ == "__main__":
    unittest.main()
