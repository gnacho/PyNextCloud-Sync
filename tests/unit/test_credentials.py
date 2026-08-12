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


class FakeSecretValue:
    def __init__(self, value: str) -> None:
        self.value = value

    def get_text(self) -> str:
        return self.value


class FakeSecretItem:
    def __init__(self, key: tuple[str, str]) -> None:
        self.key = key

    def get_locked(self) -> bool:
        return FakeSecret.locked

    def get_secret(self):
        if FakeSecret.locked:
            return None
        value = FakeSecret.saved.get(self.key)
        return FakeSecretValue(value) if value is not None else None


class FakeSecretCollection:
    @staticmethod
    def for_alias_sync(_service, alias, flags, _cancellable):
        FakeSecret.collection_aliases.append(alias)
        FakeSecret.collection_flags.append(flags)
        if FakeSecret.default_collection_missing:
            return None
        return FakeSecretCollection()

    def get_locked(self) -> bool:
        return FakeSecret.locked


class FakeSecretService:
    @staticmethod
    def get_sync(flags, _cancellable):
        FakeSecret.service_flags.append(flags)
        if FakeSecret.failure:
            raise FakeSecret.failure
        return FakeSecretService()

    def search_sync(self, _schema, attributes, flags, _cancellable):
        FakeSecret.operations.append(("search", attributes))
        FakeSecret.search_flags.append(flags)
        if FakeSecret.failure:
            raise FakeSecret.failure
        key = (attributes["server"], attributes["username"])
        if key not in FakeSecret.saved:
            return []
        if FakeSecret.hide_items_while_locked and FakeSecret.locked:
            return []
        if FakeSecret.locked and flags & FakeSecret.SearchFlags.UNLOCK:
            FakeSecret.unlock_attempts += 1
            if not FakeSecret.unlock_cancelled:
                FakeSecret.locked = False
        return [FakeSecretItem(key)]

    def unlock_sync(self, objects, _cancellable):
        FakeSecret.unlock_operations.append(tuple(objects))
        FakeSecret.unlock_attempts += 1
        if not FakeSecret.unlock_cancelled:
            FakeSecret.locked = False
            return 1, list(objects)
        return 0, []


class FakeSecret:
    Schema = FakeSchema
    SchemaFlags = types.SimpleNamespace(NONE=0)
    SchemaAttributeType = types.SimpleNamespace(STRING="string")
    Service = FakeSecretService
    Collection = FakeSecretCollection
    ServiceFlags = types.SimpleNamespace(NONE=0, OPEN_SESSION=1, LOAD_COLLECTIONS=2)
    CollectionFlags = types.SimpleNamespace(NONE=0, LOAD_ITEMS=1)
    SearchFlags = types.SimpleNamespace(NONE=0, ALL=1, UNLOCK=2, LOAD_SECRETS=4)
    COLLECTION_DEFAULT = "default"
    saved: dict[tuple[str, str], str] = {}
    operations: list[tuple[str, dict[str, str]]] = []
    service_flags: list[int] = []
    search_flags: list[int] = []
    collection_aliases: list[str] = []
    collection_flags: list[int] = []
    unlock_operations: list[tuple[object, ...]] = []
    failure: Exception | None = None
    locked = False
    unlock_cancelled = False
    unlock_attempts = 0
    hide_items_while_locked = False
    default_collection_missing = False

    @classmethod
    def reset(cls) -> None:
        cls.saved = {}
        cls.operations = []
        cls.service_flags = []
        cls.search_flags = []
        cls.collection_aliases = []
        cls.collection_flags = []
        cls.unlock_operations = []
        cls.failure = None
        cls.locked = False
        cls.unlock_cancelled = False
        cls.unlock_attempts = 0
        cls.hide_items_while_locked = False
        cls.default_collection_missing = False

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
        / "nextsync"
        / "nextcloud"
        / "credentials.py"
    )
    spec = importlib.util.spec_from_file_location(
        "nextsync_credentials_test", module_path
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
            ["store", "search", "clear"],
        )
        self.assertEqual(
            FakeSecret.service_flags,
            [
                FakeSecret.ServiceFlags.OPEN_SESSION
                | FakeSecret.ServiceFlags.LOAD_COLLECTIONS
            ],
        )
        self.assertEqual(
            FakeSecret.search_flags,
            [FakeSecret.SearchFlags.UNLOCK | FakeSecret.SearchFlags.LOAD_SECRETS],
        )
        self.assertEqual(FakeSecret.collection_aliases, [FakeSecret.COLLECTION_DEFAULT])

    def test_keyring_cancellation_is_reported_without_escaping(self) -> None:
        FakeSecret.saved[("https://cloud.example", "alice")] = "app-password"
        FakeSecret.locked = True
        FakeSecret.unlock_cancelled = True
        store = self.credentials.CredentialStore(worker_dispatch=lambda job: job())
        result = []

        store.lookup(
            "https://cloud.example",
            "alice",
            lambda password, error: result.append((password, error)),
        )

        self.assertIsNone(result[0][0])
        self.assertIsInstance(result[0][1], self.credentials.KeyringLockedError)
        self.assertEqual(FakeSecret.unlock_attempts, 1)

    def test_locked_keyring_is_unlocked_and_secret_is_loaded(self) -> None:
        FakeSecret.saved[("https://cloud.example", "alice")] = "app-password"
        FakeSecret.locked = True
        store = self.credentials.CredentialStore(worker_dispatch=lambda job: job())
        result = []

        store.lookup(
            "https://cloud.example",
            "alice",
            lambda password, error: result.append((password, error)),
        )

        self.assertEqual(result, [("app-password", None)])
        self.assertFalse(FakeSecret.locked)
        self.assertEqual(FakeSecret.unlock_attempts, 1)

    def test_explicit_collection_unlock_precedes_search_hidden_by_locked_keyring(self) -> None:
        FakeSecret.saved[("https://cloud.example", "alice")] = "app-password"
        FakeSecret.locked = True
        FakeSecret.hide_items_while_locked = True
        store = self.credentials.CredentialStore(worker_dispatch=lambda job: job())
        result = []

        store.lookup(
            "https://cloud.example",
            "alice",
            lambda password, error: result.append((password, error)),
        )

        self.assertEqual(result, [("app-password", None)])
        self.assertFalse(FakeSecret.locked)
        self.assertEqual(FakeSecret.unlock_attempts, 1)
        self.assertEqual(len(FakeSecret.unlock_operations), 1)
        self.assertEqual(
            [name for name, _attributes in FakeSecret.operations],
            ["search"],
        )

    def test_missing_item_is_not_mislabeled_as_a_locked_keyring(self) -> None:
        store = self.credentials.CredentialStore(worker_dispatch=lambda job: job())
        result = []

        store.lookup(
            "https://cloud.example",
            "alice",
            lambda password, error: result.append((password, error)),
        )

        self.assertEqual(result, [(None, None)])

    def test_unlock_result_supports_typelib_return_shapes(self) -> None:
        self.assertEqual(self.credentials.CredentialStore._unlock_count(1), 1)
        self.assertEqual(
            self.credentials.CredentialStore._unlock_count((1, [object()])), 1
        )
        self.assertEqual(self.credentials.CredentialStore._unlock_count((0, [])), 0)

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
