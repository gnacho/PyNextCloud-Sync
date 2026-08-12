from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AccountSession:
    """Per-account data and settings passed to the sync runtime.

    An account owns its synchronization and runtime settings so that adding,
    removing, or reconfiguring one account never affects the others.
    """

    account_id: str
    server_url: str
    login_name: str
    authentication_type: str
    local_root: str
    remote_path: str = ""
    sync: dict[str, Any] = field(default_factory=dict)
    delete_guard: dict[str, Any] = field(default_factory=dict)
    runtime: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_config_value(cls, account: dict[str, Any]) -> AccountSession:
        return cls(
            account_id=account.get("id", ""),
            server_url=account["server_url"],
            login_name=account["login_name"],
            authentication_type=account.get("authentication_type", "manual"),
            local_root=account["local_root"],
            remote_path=account.get("remote_path", ""),
            sync=account.get("sync", {}),
            delete_guard=account.get("delete_guard", {}),
            runtime=account.get("runtime", {}),
        )

    @property
    def local_root_path(self) -> Path:
        return Path(self.local_root).expanduser().absolute()

    @property
    def remote_path_argument(self) -> str | None:
        """Return the ``--path`` argument for ``nextcloudcmd`` or ``None`` for root mirror."""
        return self.remote_path or None

    @property
    def account_dict(self) -> dict[str, Any]:
        return {
            "server_url": self.server_url,
            "login_name": self.login_name,
            "authentication_type": self.authentication_type,
            "local_root": self.local_root,
            "remote_path": self.remote_path,
        }

    def as_account(self) -> dict[str, Any]:
        return {
            **self.account_dict,
            "sync": self.sync,
            "delete_guard": self.delete_guard,
            "runtime": self.runtime,
        }
