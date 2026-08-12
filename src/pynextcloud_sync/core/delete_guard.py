from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pynextcloud_sync.core.exclusions import ExclusionMatcher
from pynextcloud_sync.storage.config import account_fingerprint
from pynextcloud_sync.util.i18n import _
from pynextcloud_sync.util.paths import ensure_private_directory, state_dir

GUARD_FORMAT = 1

SYNC_DATABASE_RE = re.compile(r"^\.?_?sync.*\.db(?:[-.].*)?$", re.IGNORECASE)


@dataclass(frozen=True)
class DeleteAlert:
    reason: str
    message: str
    missing_paths: tuple[str, ...] = ()
    previous_count: int = 0
    current_count: int = 0

    @property
    def missing_count(self) -> int:
        return len(self.missing_paths)

    @property
    def can_approve_once(self) -> bool:
        """Allow a one-time override only for an explicit, observable deletion.

        Structural failures (missing/unreadable folder, missing manifest) always
        require the user to restore or reconfigure; they are never bypassable.
        """
        return self.reason in {"folder_emptied", "mass_local_deletion"}


class DeleteGuardManifest:
    """Per-account record of the last locally verified file set.

    This is a lightweight counterpart to nextcloudcmd's own journal: it stores
    only the sorted list of local file paths so the app can notice a mass local
    deletion before the engine propagates it to the server. No content hashes
    are computed.
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (state_dir() / "delete-guard.json")

    @classmethod
    def for_account(cls, account: dict[str, Any]) -> DeleteGuardManifest:
        return cls(state_dir() / f"delete-guard-{account_fingerprint(account)}.json")

    def load(self) -> dict[str, Any] | None:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if payload.get("format") != GUARD_FORMAT:
            return None
        return payload

    def save(self, account: dict[str, Any], files: list[str]) -> dict[str, Any]:
        payload = {
            "format": GUARD_FORMAT,
            "account_fingerprint": account_fingerprint(account),
            "local_root": str(Path(account["local_root"]).expanduser().absolute()),
            "files": sorted(files),
        }
        ensure_private_directory(self.path.parent)
        temporary = self.path.with_suffix(".tmp")
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            temporary.replace(self.path)
        finally:
            temporary.unlink(missing_ok=True)
        return payload


def is_sync_database_name(name: str) -> bool:
    return bool(SYNC_DATABASE_RE.match(name))


def find_sync_databases(root: Path) -> tuple[Path, ...]:
    """Return the nextcloudcmd journal files at the top of a sync folder."""
    try:
        return tuple(
            sorted(
                (
                    item
                    for item in root.iterdir()
                    if item.is_file() and is_sync_database_name(item.name)
                ),
                key=lambda item: item.name,
            )
        )
    except OSError:
        return ()


def scan_local_files(root: Path, matcher: ExclusionMatcher) -> list[str]:
    """Walk a sync folder and return relative file paths.

    Directories, symlinks, and special files are skipped: the guard only cares
    about regular files disappearing. Journal files and excluded patterns are
    ignored, matching what nextcloudcmd sees.
    """
    root = root.expanduser().absolute()
    files: list[str] = []
    if not root.is_dir():
        return files
    stack: list[tuple[Path, str]] = [(root, "")]
    while stack:
        directory, relative_directory = stack.pop()
        try:
            children = list(os.scandir(directory))
        except OSError:
            continue
        for child in children:
            name = child.name
            if is_sync_database_name(name) or matcher.matches_name(name):
                continue
            relative = f"{relative_directory}/{name}" if relative_directory else name
            try:
                is_dir = child.is_dir(follow_symlinks=False)
                is_file = child.is_file(follow_symlinks=False)
            except OSError:
                continue
            if is_dir:
                stack.append((Path(child.path), relative))
            elif is_file:
                files.append(relative)
    return files


class DeleteGuard:
    """Block a sync when the local tree lost too many previously known files."""

    def __init__(
        self,
        config: Any,
        logger: Any,
        manifest: DeleteGuardManifest | None = None,
    ) -> None:
        self.config = config
        self.logger = logger
        self.manifest = manifest or DeleteGuardManifest()

    def _matcher(self) -> ExclusionMatcher:
        sync = self.config.data["sync"]
        return ExclusionMatcher(
            sync.get("exclude_patterns", []),
            sync.get("exclude_patterns_enabled", True),
        )

    def check(self) -> DeleteAlert | None:
        account = self.config.data.get("account")
        guard = self.config.data.get("delete_guard", {})
        if not account or not guard.get("enabled", True):
            return None
        manifest = self.manifest.load()
        if manifest is None:
            return None
        if manifest.get("account_fingerprint") != account_fingerprint(account):
            return None

        root = Path(account["local_root"]).expanduser().absolute()
        if not root.exists() or not root.is_dir():
            return DeleteAlert(
                "folder_missing",
                _("The local synchronization folder is missing or unavailable."),
                previous_count=len(manifest.get("files", [])),
            )

        current = set(scan_local_files(root, self._matcher()))
        previous = set(manifest.get("files", []))
        missing = tuple(sorted(previous - current))
        previous_count = len(previous)
        current_count = len(current)
        if previous_count and not current_count:
            return DeleteAlert(
                "folder_emptied",
                _("A previously populated synchronization folder is now empty."),
                missing,
                previous_count,
                current_count,
            )

        count_limit = max(1, int(guard.get("count_threshold", 10)))
        percent_limit = max(1.0, min(100.0, float(guard.get("percent_threshold", 20))))
        missing_percent = (len(missing) * 100.0 / previous_count) if previous_count else 0.0
        if missing and (len(missing) >= count_limit or missing_percent >= percent_limit):
            return DeleteAlert(
                "mass_local_deletion",
                _("An unusual number of local files disappeared and could be deleted from Nextcloud."),
                missing,
                previous_count,
                current_count,
            )
        return None

    def record_current(self) -> bool:
        account = self.config.data.get("account")
        if not account:
            return False
        files = scan_local_files(Path(account["local_root"]), self._matcher())
        self.manifest.save(account, files)
        self.logger.info("Deletion guard baseline updated with %s local files.", len(files))
        return True
