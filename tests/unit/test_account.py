from __future__ import annotations

import copy
import types
import unittest

from pynextcloud_sync.core.account import AccountSession
from pynextcloud_sync.storage.config import DEFAULT_CONFIG, validate_config


class AccountSessionTests(unittest.TestCase):
    def _config(self) -> object:
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
        return types.SimpleNamespace(data=data)

    def test_from_config_builds_a_session_for_the_active_account(self) -> None:
        session = AccountSession.from_config(self._config())
        assert session is not None
        self.assertEqual(session.login_name, "alice")
        self.assertEqual(session.server_url, "https://cloud.example.com")
        self.assertEqual(session.local_root, "/tmp/NextCloud")
        self.assertEqual(session.authentication_type, "browser")
        self.assertTrue(session.account_id)

    def test_from_config_returns_none_when_unconfigured(self) -> None:
        config = types.SimpleNamespace(data=copy.deepcopy(DEFAULT_CONFIG))
        self.assertIsNone(AccountSession.from_config(config))

    def test_sync_safety_runtime_are_shared_with_config(self) -> None:
        config = self._config()
        session = AccountSession.from_config(config)
        assert session is not None
        self.assertIs(session.sync, config.data["sync"])
        self.assertIs(session.safety, config.data["safety"])
        self.assertIs(session.runtime, config.data["runtime"])

    def test_local_root_path_is_expanded_absolute(self) -> None:
        session = AccountSession.from_config(self._config())
        assert session is not None
        self.assertTrue(session.local_root_path.is_absolute())

    def test_as_account_round_trips_through_validation(self) -> None:
        session = AccountSession.from_config(self._config())
        assert session is not None
        validated = validate_config({"schema_version": 3, "accounts": [session.as_account()]})
        self.assertEqual(validated["accounts"][0]["login_name"], "alice")


if __name__ == "__main__":
    unittest.main()
