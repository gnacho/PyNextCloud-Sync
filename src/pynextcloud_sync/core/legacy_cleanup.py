from __future__ import annotations

import datetime as dt
import shutil
from pathlib import Path
from typing import Any

from pynextcloud_sync.util.paths import ensure_private_directory, state_dir


def cleanup_legacy_bootstrap(logger: Any) -> None:
    """Remove the v2.x bootstrap staging trees and archive old safety manifests.

    The thin-wrapper redesign (schema v5) removed the protected-init subsystem.
    On first run after upgrade we drop any leftover ``protected-*`` staging
    trees under ``state_dir()/bootstrap`` that the old code never cleaned on
    its own, and move legacy ``safety-manifest*.json`` files out of the way so
    the new safety-free engine can ignore them.
    """
    bootstrap_dir = state_dir() / "bootstrap"
    if bootstrap_dir.is_dir():
        removed = 0
        for entry in bootstrap_dir.iterdir():
            if entry.name.startswith("protected-"):
                try:
                    _remove_tree(entry)
                    removed += 1
                except OSError as exc:
                    logger.warning("Could not remove legacy bootstrap staging %s: %s", entry, exc)
        try:
            shutil.rmtree(bootstrap_dir)
        except OSError as exc:
            logger.warning("Could not remove the legacy bootstrap directory: %s", exc)
        if removed:
            logger.info("Removed %s leftover bootstrap staging tree(s).", removed)

    archive_dir = state_dir() / "safety-archives"
    moved = 0
    for pattern in ("safety-manifest.json", "safety-manifest-*.json"):
        for manifest in state_dir().glob(pattern):
            try:
                stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                target = archive_dir / f"legacy-{stamp}" / manifest.name
                ensure_private_directory(target.parent)
                manifest.replace(target)
                moved += 1
            except OSError as exc:
                logger.warning("Could not archive legacy safety manifest %s: %s", manifest, exc)
    if moved:
        logger.info("Archived %s legacy safety manifest(s).", moved)


def _remove_tree(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()
