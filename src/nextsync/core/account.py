from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from nextsync.storage.config import folder_fingerprint


@dataclass(frozen=True)
class FolderSession:
    """One sync folder pair (local root + remote path) inside an account."""

    folder_id: str
    local_root: str
    remote_path: str = ""

    @classmethod
    def from_config_value(cls, folder: dict[str, Any]) -> FolderSession:
        return cls(
            folder_id=folder.get("id", ""),
            local_root=folder["local_root"],
            remote_path=folder.get("remote_path", ""),
        )

    @property
    def local_root_path(self) -> Path:
        return Path(self.local_root).expanduser().absolute()

    @property
    def remote_path_argument(self) -> str | None:
        """Return the ``--path`` argument for ``nextcloudcmd`` or ``None`` for root mirror."""
        return self.remote_path or None

    @property
    def folder_dict(self) -> dict[str, Any]:
        return {
            "id": self.folder_id,
            "local_root": self.local_root,
            "remote_path": self.remote_path,
        }


@dataclass(frozen=True)
class AccountSession:
    """Per-account data and settings passed to the sync runtime.

    An account owns its synchronization and runtime settings so that adding,
    removing, or reconfiguring one account never affects the others. It may
    hold zero or more sync folders, each mapping a local root to a remote path.
    """

    account_id: str
    server_url: str
    login_name: str
    authentication_type: str
    folders: list[FolderSession] = field(default_factory=list)
    sync: dict[str, Any] = field(default_factory=dict)
    delete_guard: dict[str, Any] = field(default_factory=dict)
    runtime: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_config_value(cls, account: dict[str, Any]) -> AccountSession:
        folders = [
            FolderSession.from_config_value(folder)
            for folder in account.get("folders", [])
        ]
        return cls(
            account_id=account.get("id", ""),
            server_url=account["server_url"],
            login_name=account["login_name"],
            authentication_type=account.get("authentication_type", "manual"),
            folders=folders,
            sync=account.get("sync", {}),
            delete_guard=account.get("delete_guard", {}),
            runtime=account.get("runtime", {}),
        )

    @property
    def local_root(self) -> str:
        """First folder's local root, kept for legacy consumers."""
        return self.folders[0].local_root if self.folders else ""

    @property
    def remote_path(self) -> str:
        """First folder's remote path, kept for legacy consumers."""
        return self.folders[0].remote_path if self.folders else ""

    @property
    def local_root_path(self) -> Path:
        return Path(self.local_root).expanduser().absolute()

    @property
    def account_dict(self) -> dict[str, Any]:
        return {
            "server_url": self.server_url,
            "login_name": self.login_name,
            "authentication_type": self.authentication_type,
            "folders": [folder.folder_dict for folder in self.folders],
        }

    def as_account(self) -> dict[str, Any]:
        return {
            **self.account_dict,
            "sync": self.sync,
            "delete_guard": self.delete_guard,
            "runtime": self.runtime,
        }

    def folder(self, folder_id: str) -> FolderSession | None:
        return next(
            (folder for folder in self.folders if folder.folder_id == folder_id), None
        )


def folder_session_id(
    server_url: str, login_name: str, local_root: str, remote_path: str
) -> str:
    return folder_fingerprint(server_url, login_name, local_root, remote_path)
