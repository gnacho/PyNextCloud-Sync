from __future__ import annotations

from threading import Thread
from typing import Callable

import gi

gi.require_version("Secret", "1")
from gi.repository import GLib, Secret


SCHEMA = Secret.Schema.new(
    "com.eduhcommerce.PyNextCloudSync.Account",
    Secret.SchemaFlags.NONE,
    {
        "server": Secret.SchemaAttributeType.STRING,
        "username": Secret.SchemaAttributeType.STRING,
    },
)


class KeyringLockedError(RuntimeError):
    pass


class CredentialStore:
    def __init__(
        self,
        worker_dispatch: Callable[[Callable[[], None]], None] | None = None,
        logger: object | None = None,
    ) -> None:
        self._pending_lookups: dict[
            tuple[str, str], list[Callable[[str | None, Exception | None], None]]
        ] = {}
        self._worker_dispatch = worker_dispatch or self._start_worker
        self._logger = logger

    @staticmethod
    def _start_worker(operation: Callable[[], None]) -> None:
        Thread(
            target=operation,
            name="pynextcloud-keyring",
            daemon=True,
        ).start()

    @staticmethod
    def _on_main_thread(callback: Callable[[], None]) -> None:
        def deliver() -> bool:
            callback()
            return GLib.SOURCE_REMOVE

        GLib.idle_add(deliver)

    def _attributes(self, server: str, username: str) -> dict[str, str]:
        return {"server": server, "username": username}

    def store(
        self,
        server: str,
        username: str,
        password: str,
        callback: Callable[[bool, Exception | None], None],
    ) -> None:
        attributes = self._attributes(server, username)

        def operation() -> None:
            try:
                stored = Secret.password_store_sync(
                    SCHEMA,
                    attributes,
                    Secret.COLLECTION_DEFAULT,
                    f"PyNextCloud Sync — {username}@{server}",
                    password,
                    None,
                )
                error = None
            except Exception as exc:
                stored, error = False, self._map_error(exc)
            self._on_main_thread(lambda: callback(bool(stored), error))

        self._worker_dispatch(operation)

    def lookup(
        self,
        server: str,
        username: str,
        callback: Callable[[str | None, Exception | None], None],
    ) -> None:
        attributes = self._attributes(server, username)
        key = (server, username)
        if key in self._pending_lookups:
            self._pending_lookups[key].append(callback)
            return
        self._pending_lookups[key] = [callback]

        def operation() -> None:
            try:
                password, error = self._lookup_with_unlock(attributes), None
            except KeyringLockedError as exc:
                password, error = None, exc
            except Exception as exc:
                password, error = None, self._map_error(exc)

            def deliver() -> None:
                callbacks = self._pending_lookups.pop(key, [])
                for pending_callback in callbacks:
                    pending_callback(password, error)

            self._on_main_thread(deliver)

        self._worker_dispatch(operation)

    def _lookup_with_unlock(self, attributes: dict[str, str]) -> str | None:
        service = Secret.Service.get_sync(
            Secret.ServiceFlags.OPEN_SESSION | Secret.ServiceFlags.LOAD_COLLECTIONS,
            None,
        )
        if service is None:
            raise RuntimeError("The desktop Secret Service is unavailable")

        # A biometric desktop login can leave the default Login collection
        # locked. On GNOME Keyring, searching immediately during autostart may
        # then return no items at all, even with SECRET_SEARCH_UNLOCK. Resolve
        # and unlock the collection itself first so its items become visible to
        # the subsequent attribute search.
        collection = Secret.Collection.for_alias_sync(
            service,
            Secret.COLLECTION_DEFAULT,
            Secret.CollectionFlags.NONE,
            None,
        )
        if collection is not None and collection.get_locked():
            self._log_info(
                "The default password keyring is locked; requesting the native unlock prompt."
            )
            unlock_result = service.unlock_sync([collection], None)
            if self._unlock_count(unlock_result) < 1 and collection.get_locked():
                raise KeyringLockedError("The password keyring remains locked")

        items = service.search_sync(
            SCHEMA,
            attributes,
            Secret.SearchFlags.UNLOCK | Secret.SearchFlags.LOAD_SECRETS,
            None,
        )
        if not items:
            self._log_warning(
                "Secret Service returned no matching credential after the default keyring was checked."
            )
            return None

        item = items[0]
        secret = item.get_secret()
        if secret is not None:
            password = secret.get_text()
            if password is not None:
                return password

        if item.get_locked():
            raise KeyringLockedError("The password keyring remains locked")
        raise RuntimeError("The stored account credential could not be loaded")

    def _log_info(self, message: str) -> None:
        if self._logger is not None:
            self._logger.info(message)

    def _log_warning(self, message: str) -> None:
        if self._logger is not None:
            self._logger.warning(message)

    @staticmethod
    def _unlock_count(result: object) -> int:
        # PyGObject exposes the C return value either directly or as the first
        # element of a tuple followed by the out-parameter list, depending on
        # the typelib version.
        value = result[0] if isinstance(result, tuple) and result else result
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    def clear(
        self,
        server: str,
        username: str,
        callback: Callable[[bool, Exception | None], None] | None = None,
    ) -> None:
        attributes = self._attributes(server, username)

        def operation() -> None:
            try:
                cleared = Secret.password_clear_sync(SCHEMA, attributes, None)
                error = None
            except Exception as exc:
                cleared, error = False, self._map_error(exc)
            if callback:
                self._on_main_thread(lambda: callback(bool(cleared), error))

        self._worker_dispatch(operation)

    @staticmethod
    def _map_error(error: Exception) -> Exception:
        text = str(error).lower()
        if "locked" in text or "cancel" in text or "dismiss" in text:
            return KeyringLockedError(str(error))
        return RuntimeError(str(error))
