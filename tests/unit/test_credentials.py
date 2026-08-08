from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


class FakeSecretError(Exception):
    pass


class FakeSchema:
    @staticmethod
    def new(name, flags, attributes):
        return name, flags, attributes


class FakeSecret:
    Schema = FakeSchema
    SchemaFlags = types.SimpleNamespace(NONE=0)
    SchemaAttributeType = types.SimpleNamespace(STRING="string")
    COLLECTION_DEFAULT = "default"
    saved: dict[tuple[str, str], str] = {}
    operations: list[tuple[str, dict[str, str]]] = []
    failure: Exception | None = None

    @classmethod
    def reset(cls) -> None:
        cls.saved = {}
        cls.operations = []
        cls.failure = None

    @classmethod
    def password_store_sync(
        cls, _schema, attributes, _collection, _label, password, _cancellable
    ):
        cls.operations.append(("store", attributes))
        if cls.failure:
            raise cls.failure
        cls.saved[(attributes["server"], attributes["username"])] = password
        return True

    @classmethod
    def password_lookup_sync(cls, _schema, attributes, _cancellable):
        cls.operations.append(("lookup", attributes))
        if cls.failure:
            raise cls.failure
        return cls.saved.get((attributes["server"], attributes["username"]))

    @classmethod
    def password_clear_sync(cls, _schema, attributes, _cancellable):
        cls.operations.append(("clear", attributes))
        if cls.failure:
            raise cls.failure
        return cls.saved.pop(
            (attributes["server"], attributes["username"]), None
        ) is not None


class FakeGLib:
    Error = FakeSecretError
    SOURCE_REMOVE = False

    @staticmethod
    def idle_add(callback):
        callback()
        return 1


def load_credentials_module():
    fake_gi = types.ModuleType("gi")
    fake_gi.require_version = lambda *_args: None
    fake_repository = types.ModuleType("gi.repository")
    fake_repository.GLib = FakeGLib
    fake_repository.Secret = FakeSecret
    module_path = (
        Path(__file__).parents[2]
        / "src"
        / "pynextcloud_sync"
        / "nextcloud"
        / "credentials.py"
    )
    spec = importlib.util.spec_from_file_location(
        "pynextcloud_sync_credentials_test", module_path
    )
    module = importlib.util.module_from_spec(spec)
    with patch.dict(
        sys.modules,
        {"gi": fake_gi, "gi.repository": fake_repository},
    ):
        assert spec.loader is not None
        spec.loader.exec_module(module)
    return module


class CredentialStoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.credentials = load_credentials_module()

    def setUp(self) -> None:
        FakeSecret.reset()

    def test_store_lookup_and_clear_use_compatible_sync_api(self) -> None:
        store = self.credentials.CredentialStore(worker_dispatch=lambda job: job())
        stored = []
        looked_up = []
        cleared = []

        store.store(
            "https://cloud.example",
            "alice",
            "app-password",
            lambda ok, error: stored.append((ok, error)),
        )
        store.lookup(
            "https://cloud.example",
            "alice",
            lambda password, error: looked_up.append((password, error)),
        )
        store.clear(
            "https://cloud.example",
            "alice",
            lambda ok, error: cleared.append((ok, error)),
        )

        self.assertEqual(stored, [(True, None)])
        self.assertEqual(looked_up, [("app-password", None)])
        self.assertEqual(cleared, [(True, None)])
        self.assertEqual(
            [name for name, _attributes in FakeSecret.operations],
            ["store", "lookup", "clear"],
        )

    def test_keyring_cancellation_is_reported_without_escaping(self) -> None:
        FakeSecret.failure = FakeSecretError("Prompt was dismissed by the user")
        store = self.credentials.CredentialStore(worker_dispatch=lambda job: job())
        result = []

        store.store(
            "https://cloud.example",
            "alice",
            "app-password",
            lambda ok, error: result.append((ok, error)),
        )

        self.assertFalse(result[0][0])
        self.assertIsInstance(result[0][1], self.credentials.KeyringLockedError)

    def test_simultaneous_lookups_are_coalesced(self) -> None:
        FakeSecret.saved[("https://cloud.example", "alice")] = "app-password"
        jobs = []
        store = self.credentials.CredentialStore(worker_dispatch=jobs.append)
        results = []

        store.lookup(
            "https://cloud.example",
            "alice",
            lambda password, error: results.append(("first", password, error)),
        )
        store.lookup(
            "https://cloud.example",
            "alice",
            lambda password, error: results.append(("second", password, error)),
        )

        self.assertEqual(len(jobs), 1)
        jobs[0]()
        self.assertEqual(
            results,
            [
                ("first", "app-password", None),
                ("second", "app-password", None),
            ],
        )


if __name__ == "__main__":
    unittest.main()
