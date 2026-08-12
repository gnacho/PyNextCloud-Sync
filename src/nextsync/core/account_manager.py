from __future__ import annotations

from typing import Any, Callable

from nextsync.core.account import AccountSession, FolderSession
from nextsync.core.runtime import RuntimeController
from nextsync.core.state import (
    AggregateStateController,
    AppState,
    StateController,
)
from nextsync.core.sync_permit import SyncPermit
from nextsync.util.i18n import _


def _folder_session(account: AccountSession, folder: FolderSession) -> AccountSession:
    """Return an account session scoped to one folder for runtime consumption.

    The runtime and scheduler read the sync folder through the legacy
    ``config.data["account"]`` view. Scoping the session to a single folder lets
    the unmodified RuntimeController handle one pair per account; the shared
    watchers (network, power, suspend) are owned once per account below.
    """
    return AccountSession(
        account_id=account.account_id,
        server_url=account.server_url,
        login_name=account.login_name,
        authentication_type=account.authentication_type,
        folders=[folder],
        sync=account.sync,
        delete_guard=account.delete_guard,
        runtime=account.runtime,
    )


class FolderConfigView:
    """A config-like facade bound to one folder of one account.

    Serves exactly the keys the runtime and scheduler expect
    (``data["account"]``, ``data["sync"]``, ``data["delete_guard"]``,
    ``data["runtime"]``) scoped to this folder, delegating global sections and
    persistence to the real store.
    """

    def __init__(self, store: Any, session: AccountSession) -> None:
        self._store = store
        self._session = session
        self._listeners: list[Callable[[dict[str, Any]], None]] = []

    @property
    def configured(self) -> bool:
        return bool(self._session.folders)

    @property
    def accounts(self) -> list[dict[str, Any]]:
        return [self._session.as_account()]

    @property
    def data(self) -> dict[str, Any]:
        session = self._session
        store_data = self._store.data
        folder = session.folders[0] if session.folders else None
        return {
            "schema_version": store_data.get("schema_version"),
            "accounts": [session.as_account()],
            "account": {
                "id": session.account_id,
                "server_url": session.server_url,
                "login_name": session.login_name,
                "authentication_type": session.authentication_type,
                "local_root": folder.local_root if folder else "",
                "remote_path": folder.remote_path if folder else "",
            },
            "folders": [item.folder_dict for item in session.folders],
            "sync": session.sync,
            "delete_guard": session.delete_guard,
            "runtime": session.runtime,
            "general": store_data.get("general", {}),
            "logging": store_data.get("logging", {}),
            "network": store_data.get("network", {}),
        }

    def save(self, *, notify: bool = True) -> None:
        self._sync_back()
        self._store.save(notify=notify)
        if notify:
            for listener in tuple(self._listeners):
                listener(self.data)

    def subscribe(self, callback: Callable[[dict[str, Any]], None]) -> Callable[[], None]:
        self._listeners.append(callback)

        def unsubscribe() -> None:
            if callback in self._listeners:
                self._listeners.remove(callback)

        return unsubscribe

    def _sync_back(self) -> None:
        for account in self._store.data.get("accounts", []):
            if account.get("id") == self._session.account_id:
                account["sync"] = self._session.sync
                account["delete_guard"] = self._session.delete_guard
                account["runtime"] = self._session.runtime
                return


class FolderRuntime:
    """A running synchronization runtime for one folder pair of an account."""

    def __init__(
        self,
        config: Any,
        credentials: Any,
        logger: Any,
        account: AccountSession,
        folder: FolderSession,
        notify_failure: Callable[[Any], None] | None = None,
        notify_delete_alert: Callable[[Any], None] | None = None,
        sync_permit: SyncPermit | None = None,
    ) -> None:
        self.folder = folder
        self.session = _folder_session(account, folder)
        self.view = FolderConfigView(config, self.session)
        wrapped_failure = (
            (lambda result: notify_failure(account.login_name, result))
            if notify_failure
            else None
        )
        wrapped_delete_alert = (
            (lambda alert: notify_delete_alert(account.login_name, alert))
            if notify_delete_alert
            else None
        )
        self.runtime = RuntimeController(
            self.view,
            credentials,
            logger,
            wrapped_failure,
            wrapped_delete_alert,
            sync_permit=sync_permit,
        )

    @property
    def state(self) -> StateController:
        return self.runtime.state

    def start(self) -> None:
        self.runtime.start()

    def stop(self) -> None:
        self.runtime.stop()


class _AccountEngines:
    """Aggregate ``running`` across every folder engine of an account."""

    def __init__(self, folders: dict[str, FolderRuntime]) -> None:
        self._folders = folders

    @property
    def running(self) -> bool:
        return any(
            folder_runtime.runtime.engine.running
            for folder_runtime in self._folders.values()
        )


class AccountRuntime:
    """One account with zero or more running folder runtimes."""

    def __init__(
        self,
        config: Any,
        credentials: Any,
        logger: Any,
        session: AccountSession,
        notify_failure: Callable[[Any], None] | None = None,
        notify_delete_alert: Callable[[Any], None] | None = None,
        sync_permit: SyncPermit | None = None,
    ) -> None:
        self.session = session
        self.config = config
        self._credentials = credentials
        self._logger = logger
        self._notify_failure = notify_failure
        self._notify_delete_alert = notify_delete_alert
        self._sync_permit = sync_permit
        self._folders: dict[str, FolderRuntime] = {}
        self._aggregate = AggregateStateController()

    @property
    def account_id(self) -> str:
        return self.session.account_id

    @property
    def display_name(self) -> str:
        return self.session.login_name

    @property
    def state(self) -> StateController:
        return self._aggregate

    @property
    def folders(self) -> dict[str, FolderRuntime]:
        return self._folders

    @property
    def scheduler(self) -> Any:
        """First folder scheduler, kept for the active-account control API."""
        if not self._folders:
            return None
        return next(iter(self._folders.values())).runtime.scheduler

    @property
    def engine(self) -> Any:
        return _AccountEngines(self._folders)

    def sync_now(self) -> None:
        for folder_runtime in self._folders.values():
            folder_runtime.runtime.sync_now()

    def set_paused(self, paused: bool) -> None:
        for folder_runtime in self._folders.values():
            folder_runtime.runtime.set_paused(paused)

    def approve_delete_once(self) -> None:
        for folder_runtime in self._folders.values():
            folder_runtime.runtime.approve_delete_once()

    def restore_from_server(self) -> None:
        for folder_runtime in self._folders.values():
            folder_runtime.runtime.restore_from_server()

    def _ensure_folder(self, folder: FolderSession) -> None:
        if folder.folder_id in self._folders:
            return
        folder_runtime = FolderRuntime(
            self.config,
            self._credentials,
            self._logger,
            self.session,
            folder,
            self._notify_failure,
            self._notify_delete_alert,
            self._sync_permit,
        )
        folder_runtime.start()
        self._folders[folder.folder_id] = folder_runtime
        self._aggregate.add(folder_runtime.state)

    def start(self) -> None:
        if not self.session.folders:
            idle = StateController(AppState.IDLE_OK)
            idle.set(AppState.IDLE_OK, _("Connected. Add folders from Settings."))
            self._aggregate.add(idle)
            return
        for folder in self.session.folders:
            self._ensure_folder(folder)

    def stop(self) -> None:
        for folder_runtime in tuple(self._folders.values()):
            folder_runtime.stop()
        self._folders.clear()
        self._aggregate.clear()


class AccountManager:
    """Owns one AccountRuntime per configured account."""

    def __init__(
        self,
        config: Any,
        credentials: Any,
        logger: Any,
        notify_failure: Callable[[Any], None] | None = None,
        notify_delete_alert: Callable[[Any], None] | None = None,
    ) -> None:
        self.config = config
        self.credentials = credentials
        self.logger = logger
        self.notify_failure = notify_failure
        self.notify_delete_alert = notify_delete_alert
        self._runtimes: dict[str, AccountRuntime] = {}
        self._session_cache: dict[str, AccountSession] = {}
        self._aggregate = AggregateStateController()
        self.sync_permit = SyncPermit()
        self._refresh_sessions()

    @property
    def runtimes(self) -> dict[str, AccountRuntime]:
        return self._runtimes

    @property
    def aggregate_state(self) -> AggregateStateController:
        return self._aggregate

    @property
    def sessions(self) -> dict[str, AccountSession]:
        return self._session_cache

    @property
    def active_ids(self) -> list[str]:
        return [account["id"] for account in self.config.accounts]

    def _refresh_sessions(self) -> None:
        cache: dict[str, AccountSession] = {}
        for account in self.config.accounts:
            session = AccountSession.from_config_value(account)
            cache[session.account_id] = session
        self._session_cache = cache

    def start(self) -> None:
        self._refresh_sessions()
        for account_id, session in self._session_cache.items():
            self._ensure_runtime(account_id, session)

    def _ensure_runtime(self, account_id: str, session: AccountSession) -> None:
        if account_id in self._runtimes:
            return
        runtime = AccountRuntime(
            self.config,
            self.credentials,
            self.logger,
            session,
            self.notify_failure,
            self.notify_delete_alert,
            self.sync_permit,
        )
        runtime.start()
        self._runtimes[account_id] = runtime
        self._aggregate.add(runtime.state)

    def ensure_account_runtime(self, account_id: str) -> None:
        """Start the runtime for one account when it is not already running."""
        if account_id in self._runtimes:
            return
        self._refresh_sessions()
        session = self._session_cache.get(account_id)
        if session:
            self._ensure_runtime(account_id, session)

    def stop(self) -> None:
        for runtime in tuple(self._runtimes.values()):
            runtime.stop()
        self._runtimes.clear()
        self._aggregate.clear()

    def remove(self, account_id: str) -> bool:
        """Stop and drop a single account runtime, leaving the rest running."""
        runtime = self._runtimes.pop(account_id, None)
        if runtime is None:
            return False
        runtime.stop()
        self._aggregate.remove(runtime.state)
        self._session_cache.pop(account_id, None)
        return True

    def get(self, account_id: str) -> AccountRuntime | None:
        return self._runtimes.get(account_id)
