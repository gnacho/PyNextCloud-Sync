from __future__ import annotations

import unittest

from pynextcloud_sync.core.account import AccountSession
from pynextcloud_sync.storage.config import validate_config


def _account_value() -> dict:
    data = validate_config(
        {
            "schema_version": 3,
            "accounts": [
                {
                    "server_url": "https://cloud.example.com",
                    "login_name": "alice",
                    "authentication_type": "browser",
                    "local_root": "/tmp/NextCloud",
                }
            ],
        }
    )
    return data["accounts"][0]


class AccountSessionTests(unittest.TestCase):
    def test_from_config_value_builds_a_session(self) -> None:
        session = AccountSession.from_config_value(_account_value())
        self.assertEqual(session.login_name, "alice")
        self.assertEqual(session.server_url, "https://cloud.example.com")
        self.assertEqual(session.local_root, "/tmp/NextCloud")
        self.assertEqual(session.authentication_type, "browser")
        self.assertTrue(session.account_id)

    def test_from_config_value_keeps_per_account_settings(self) -> None:
        value = _account_value()
        value["sync"]["max_sync_retries"] = 5
        session = AccountSession.from_config_value(value)
        self.assertEqual(session.sync["max_sync_retries"], 5)
        self.assertEqual(session.safety, value["safety"])
        self.assertEqual(session.runtime, value["runtime"])

    def test_local_root_path_is_expanded_absolute(self) -> None:
        session = AccountSession.from_config_value(_account_value())
        self.assertTrue(session.local_root_path.is_absolute())

    def test_as_account_round_trips_through_validation(self) -> None:
        session = AccountSession.from_config_value(_account_value())
        validated = validate_config(
            {"schema_version": 3, "accounts": [session.as_account()]}
        )
        self.assertEqual(validated["accounts"][0]["login_name"], "alice")

    def test_from_config_value_defaults_remote_path_to_root(self) -> None:
        session = AccountSession.from_config_value(_account_value())
        self.assertEqual(session.remote_path, "")
        self.assertIsNone(session.remote_path_argument)

    def test_from_config_value_carries_remote_path(self) -> None:
        value = _account_value()
        value["remote_path"] = "/Documents"
        session = AccountSession.from_config_value(value)
        self.assertEqual(session.remote_path, "/Documents")
        self.assertEqual(session.remote_path_argument, "/Documents")
        self.assertEqual(session.account_dict["remote_path"], "/Documents")


if __name__ == "__main__":
    unittest.main()
