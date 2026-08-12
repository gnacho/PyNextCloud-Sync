from __future__ import annotations

import datetime as dt
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


CONFLICT_RE = re.compile(
    r"^(?P<stem>.*?) \(Nextcloud conflicted copy "
    r"(?P<date>\d{4}-\d{2}-\d{2}(?:[- ][\d: -]+)?)\)"
    r"(?P<extension>\.[^.]*)?$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ConflictFile:
    """One ``* (Nextcloud conflicted copy <date>).*`` file found in a sync root."""

    path: Path
    original_name: str
    original_path: Path
    conflict_date: str
    size: int
    modified: float

    @property
    def name(self) -> str:
        return self.path.name

    def description(self) -> str:
        return f"{self.original_name} · {self.path.name}"


def find_conflicts(
    root: Path,
    *,
    progress: Callable[[int, int], None] | None = None,
) -> list[ConflictFile]:
    """Walk a sync folder and return conflicted copies produced by nextcloudcmd.

    Only regular files matching the engine's conflicted-copy naming pattern are
    returned. The original path is derived from the file name by stripping the
    conflict suffix, so the "original" may not exist locally.
    """
    root = root.expanduser().absolute()
    matches: list[ConflictFile] = []
    if not root.is_dir():
        return matches

    candidates: list[Path] = []
    for path in root.rglob("*"):
        if path.is_file():
            candidates.append(path)
    total = len(candidates)
    for index, path in enumerate(candidates, start=1):
        if progress:
            progress(index, total)
        match = CONFLICT_RE.match(path.name)
        if not match:
            continue
        stem = match.group("stem")
        extension = match.group("extension") or ""
        if stem.lower().endswith(extension.lower()):
            original_name = stem
        else:
            original_name = stem + extension
        original_path = path.with_name(original_name)
        try:
            details = path.stat()
        except OSError:
            continue
        matches.append(
            ConflictFile(
                path=path,
                original_name=original_name,
                original_path=original_path,
                conflict_date=match.group("date"),
                size=int(details.st_size),
                modified=details.st_mtime,
            )
        )
    matches.sort(key=lambda item: item.path.name)
    return matches


def conflict_iso_date(value: str) -> str:
    """Return an ISO-ish timestamp for display from the conflicted-copy date."""
    cleaned = value.strip().replace(" ", "T")
    return cleaned


def keep_local(conflict: ConflictFile) -> bool:
    """Delete the conflicted copy, keeping the working file in place."""
    try:
        if conflict.path.exists():
            conflict.path.unlink()
        return True
    except OSError:
        return False


def keep_remote(conflict: ConflictFile) -> bool:
    """Replace the local working file with the conflicted copy.

    The conflicted copy is the engine's version of the remote content; keeping
    it promotes that content over whatever the local working file holds.
    """
    try:
        shutil.copy2(conflict.path, conflict.original_path)
        return True
    except OSError:
        return False


def describe_modified(timestamp: float) -> str:
    try:
        return dt.datetime.fromtimestamp(timestamp).strftime("%x %H:%M")
    except (OSError, ValueError, OverflowError):
        return ""
