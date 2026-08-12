from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SyncProgress:
    """One parsed progress event from nextcloudcmd output.

    ``processed`` counts operations reported so far in the current sync when a
    total is unavailable; it starts at 1 for the first parsed line.
    """

    action: str
    path: str
    processed: int = 0

    @property
    def is_operation(self) -> bool:
        return self.action in {"download", "upload", "delete", "conflict"}


_ACTION_ALIASES = {
    "downloading": "download",
    "download": "download",
    "download started": "download",
    "uploading": "upload",
    "upload": "upload",
    "upload started": "upload",
    "deleting": "delete",
    "delete": "delete",
    "removing": "delete",
    "synced": "synced",
    "skipped": "skipped",
    "conflict": "conflict",
    "conflicted copy": "conflict",
}

# nextcloudcmd prints one file operation per line, e.g.
# "Downloading: path/to/file" or "Uploading: folder/file". The action word is
# followed by a colon and an optional Windows-style drive prefix. Anything
# that does not look like an operation is treated as an unknown line and the
# caller forwards it as raw text.
_OPERATION_RE = re.compile(
    r"^\s*(?P<action>[A-Za-z]+(?:[ ][A-Za-z]+)*)\s*:\s*(?P<path>[A-Za-z]:/.*|/.*|\.{1,2}/.*|\S.*)$"
)


def parse_progress_line(line: str) -> SyncProgress | None:
    """Parse one nextcloudcmd stdout line into a SyncProgress, if possible.

    Returns ``None`` for lines that do not look like a per-file operation so
    the caller can forward them verbatim without guessing.
    """
    stripped = (line or "").strip()
    if not stripped:
        return None
    match = _OPERATION_RE.match(stripped)
    if not match:
        return None
    raw_action = match.group("action").lower()
    action = _ACTION_ALIASES.get(raw_action)
    if action is None:
        return None
    path = match.group("path").strip().strip('"')
    return SyncProgress(action=action, path=path)


def describe_progress(progress: SyncProgress | None) -> str:
    """Return a short human label for a SyncProgress value."""
    if progress is None:
        return ""
    if progress.is_operation and progress.processed > 0:
        return f"{progress.action}: {progress.path} ({progress.processed})"
    return f"{progress.action}: {progress.path}"
