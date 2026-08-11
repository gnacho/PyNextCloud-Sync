from __future__ import annotations

from typing import Any, Callable

from pynextcloud_sync.core.account import AccountSession
from pynextcloud_sync.core.runtime import RuntimeController
from pynextcloud_sync.core.state import (
    AggregateStateController,
    AppState,
    StateController,
)


class AccountConfigView:
    """A config-like facade bound to one account.

    Existing runtime and scheduler code reads a single account through
    ``config.data["account"]``, ``config.data["sync"]``, and so on. This view
    serves exactly those keys from the account's own settings while delegating
    global sections (network, general, logging) and persistence to the real
    store, so per-account runtimes stay isolated.
    """

    def __init__(self, store: Any, session: AccountSession) -> None:
        self._store = store
        self._session = session
        self._listeners: list[Callable[[dict[str, Any]], None]] = []

    @property
    def configured(self) -> bool:
        return True

    @property
    def accounts(self) -> list[dict[str, Any]]:
        return [self._session.as_account()]

    @property
    def data(self) -> dict[str, Any]:
        session = self._session
        store_data = self._store.data
        return {
            "schema_version": store_data.get("schema_version"),
            "accounts": [session.as_account()],
            "account": session.account_dict,
            "sync": session.sync,
            "safety": session.safety,
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
                account["safety"] = self._session.safety
                account["runtime"] = self._session.runtime
                return


class AccountRuntime:
    """A running synchronization runtime for one account."""

    def __init__(
        self,
        config: Any,
        credentials: Any,
        logger: Any,
        session: AccountSession,
        notify_failure: Callable[[Any], None] | None = None,
        notify_safety_alert: Callable[[Any], None] | None = None,
    ) -> None:
        self.session = session
        self.view = AccountConfigView(config, session)
        self.runtime = RuntimeController(
            self.view,
            credentials,
            logger,
            notify_failure,
            notify_safety_alert,
        )

    @property
    def state(self) -> StateController:
        return self.runtime.state

    @property
    def account_id(self) -> str:
        return self.session.account_id

    @property
    def display_name(self) -> str:
        return self.session.login_name

    def start(self) -> None:
        self.runtime.start()

    def stop(self) -> None:
        self.runtime.stop()


class AccountManager:
    """Owns one AccountRuntime per configured account."""

    def __init__(
        self,
        config: Any,
        credentials: Any,
        logger: Any,
        notify_failure: Callable[[Any], None] | None = None,
        notify_safety_alert: Callable[[Any], None] | None = None,
    ) -> None:
        self.config = config
        self.credentials = credentials
        self.logger = logger
        self.notify_failure = notify_failure
        self.notify_safety_alert = notify_safety_alert
        self._runtimes: dict[str, AccountRuntime] = {}
        self._session_cache: dict[str, AccountSession] = {}
        self._aggregate = AggregateStateController()
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
            if not account.get("safety", {}).get("bootstrap_complete", False):
                continue
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
            self.notify_safety_alert,
        )
        runtime.start()
        self._runtimes[account_id] = runtime
        self._aggregate.add(runtime.state)

    def ensure_account_runtime(self, account_id: str) -> None:
        """Start the runtime for one account after its bootstrap completes."""
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

    def get(self, account_id: str) -> AccountRuntime | None:
        return self._runtimes.get(account_id)
