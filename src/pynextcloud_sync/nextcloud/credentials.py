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
    ) -> None:
        self._pending_lookups: dict[
            tuple[str, str], list[Callable[[str | None, Exception | None], None]]
        ] = {}
        self._worker_dispatch = worker_dispatch or self._start_worker

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
                password, error = Secret.password_lookup_sync(
                    SCHEMA, attributes, None
                ), None
            except Exception as exc:
                password, error = None, self._map_error(exc)

            def deliver() -> None:
                callbacks = self._pending_lookups.pop(key, [])
                for pending_callback in callbacks:
                    pending_callback(password, error)

            self._on_main_thread(deliver)

        self._worker_dispatch(operation)

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
