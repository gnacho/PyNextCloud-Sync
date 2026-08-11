from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit, urlunsplit

from pynextcloud_sync.core.exclusions import DEFAULT_PATTERNS, validate_pattern
from pynextcloud_sync.util.paths import config_dir, default_sync_root, ensure_private_directory


SCHEMA_VERSION = 4

DEFAULT_SYNC: dict[str, Any] = {
    "local_inotify_enabled": True,
    "local_interval_enabled": False,
    "local_interval_minutes": 5,
    "remote_push_enabled": True,
    "remote_interval_enabled": True,
    "remote_interval_minutes": 10,
    "max_sync_retries": 3,
    "detailed_output": True,
    "exclude_patterns_enabled": True,
    "exclude_patterns": list(DEFAULT_PATTERNS),
}

DEFAULT_SAFETY: dict[str, Any] = {
    "bootstrap_complete": False,
    "bootstrap_completed_at": None,
    "guard_enabled": True,
    "deletion_count_threshold": 10,
    "deletion_percent_threshold": 20,
}

DEFAULT_RUNTIME: dict[str, Any] = {
    "last_successful_sync": None,
    "last_exit_code": None,
}

DEFAULT_CONFIG: dict[str, Any] = {
    "schema_version": SCHEMA_VERSION,
    "accounts": [],
    "general": {"autostart": True, "pause_on_battery": False},
    "logging": {"save_logs": True, "retention_days": 30},
    "network": {"custom_proxy": None, "trust_invalid_certificates": False},
    # Legacy single-account view, kept in memory as a live alias of the first
    # account so existing code keeps working while sessions are introduced.
    "account": None,
    "sync": DEFAULT_SYNC,
    "safety": DEFAULT_SAFETY,
    "runtime": DEFAULT_RUNTIME,
}


class ConfigurationError(ValueError):
    pass


def normalize_server_url(value: str) -> str:
    candidate = value.strip()
    parsed = urlsplit(candidate)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        raise ConfigurationError("Enter a complete HTTP or HTTPS Nextcloud URL.")
    if parsed.username or parsed.password:
        raise ConfigurationError("Credentials must not be included in the server URL.")
    path = parsed.path.rstrip("/")
    return urlunsplit((parsed.scheme.lower(), parsed.netloc, path, "", ""))


def normalize_remote_path(value: Any) -> str:
    """Normalize a remote folder path.

    Returns an empty string for the account root (the Nextcloud server root),
    which the sync layer treats as a plain root-to-root mirror (no ``--path``
    argument passed to ``nextcloudcmd``). Any non-root value is returned as an
    absolute Unix-style path without trailing slash, e.g. ``/Documents``.
    """
    raw = str(value or "").strip()
    if not raw or raw == "/":
        return ""
    if "\\" in raw or "\0" in raw:
        raise ConfigurationError("The remote folder may not contain backslashes or null bytes.")
    if raw.startswith("http://") or raw.startswith("https://"):
        raise ConfigurationError("The remote folder must be a path, not a full URL.")
    if any(token in raw for token in ("?", "#")):
        raise ConfigurationError("The remote folder may not include query parameters or fragments.")
    if not raw.startswith("/"):
        raw = "/" + raw
    segments: list[str] = []
    for segment in raw.split("/"):
        if segment in ("", "."):
            continue
        if segment == "..":
            raise ConfigurationError("The remote folder may not contain parent directory references.")
        segments.append(segment)
    if not segments:
        return ""
    return "/" + "/".join(segments)


def account_fingerprint(account: dict[str, Any]) -> str:
    identity = "\n".join(
        (
            str(account.get("server_url", "")).rstrip("/").casefold(),
            str(account.get("login_name", "")).casefold(),
            str(Path(str(account.get("local_root", ""))).expanduser().absolute()),
            str(account.get("remote_path", "")),
        )
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _deep_merge(defaults: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(defaults)
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _validate_sync(sync: dict[str, Any]) -> dict[str, Any]:
    merged = _deep_merge(DEFAULT_SYNC, sync)
    for key, lower, upper in (
        ("local_interval_minutes", 1, 1440),
        ("remote_interval_minutes", 1, 1440),
        ("max_sync_retries", 1, 10),
    ):
        try:
            value = int(merged[key])
        except (KeyError, TypeError, ValueError) as exc:
            raise ConfigurationError(f"Invalid setting: {key}") from exc
        if not lower <= value <= upper:
            raise ConfigurationError(f"{key} must be between {lower} and {upper}.")
        merged[key] = value
    merged["exclude_patterns"] = [
        validate_pattern(str(pattern)) for pattern in merged.get("exclude_patterns", [])
    ]
    return merged


def _validate_safety(safety: dict[str, Any]) -> dict[str, Any]:
    merged = _deep_merge(DEFAULT_SAFETY, safety)
    merged["bootstrap_complete"] = bool(merged.get("bootstrap_complete", False))
    merged["guard_enabled"] = bool(merged.get("guard_enabled", True))
    try:
        deletion_count = int(merged.get("deletion_count_threshold", 10))
        deletion_percent = int(merged.get("deletion_percent_threshold", 20))
    except (TypeError, ValueError) as exc:
        raise ConfigurationError("Invalid safety deletion threshold.") from exc
    if not 1 <= deletion_count <= 100_000:
        raise ConfigurationError("deletion_count_threshold must be between 1 and 100000.")
    if not 1 <= deletion_percent <= 100:
        raise ConfigurationError("deletion_percent_threshold must be between 1 and 100.")
    merged["deletion_count_threshold"] = deletion_count
    merged["deletion_percent_threshold"] = deletion_percent
    return merged


def _validate_runtime(runtime: dict[str, Any]) -> dict[str, Any]:
    return _deep_merge(DEFAULT_RUNTIME, runtime)


def _migrate_to_v3(data: dict[str, Any]) -> dict[str, Any]:
    if "accounts" in data or "account" not in data:
        return data
    account = data.get("account")
    if account is None:
        accounts: list[dict[str, Any]] = []
    else:
        accounts = [
            {
                "server_url": account.get("server_url", ""),
                "login_name": account.get("login_name", ""),
                "authentication_type": account.get("authentication_type", "manual"),
                "local_root": account.get("local_root", ""),
                "remote_path": account.get("remote_path", ""),
                "sync": data.get("sync", DEFAULT_SYNC),
                "safety": data.get("safety", DEFAULT_SAFETY),
                "runtime": data.get("runtime", DEFAULT_RUNTIME),
            }
        ]
    migrated = dict(data)
    migrated["accounts"] = accounts
    migrated.pop("account", None)
    migrated.pop("sync", None)
    migrated.pop("safety", None)
    migrated.pop("runtime", None)
    return migrated


def _validate_account(account: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(account, dict):
        raise ConfigurationError("Account configuration is invalid.")
    validated: dict[str, Any] = {
        "server_url": normalize_server_url(str(account.get("server_url", ""))),
        "login_name": str(account.get("login_name", "")).strip(),
        "authentication_type": account.get("authentication_type", "manual"),
    }
    if not validated["login_name"]:
        raise ConfigurationError("Account username is missing.")
    root = Path(str(account.get("local_root", default_sync_root()))).expanduser()
    if not root.is_absolute():
        raise ConfigurationError("The local synchronization folder must be absolute.")
    validated["local_root"] = str(root)
    validated["remote_path"] = normalize_remote_path(account.get("remote_path", ""))
    validated["sync"] = _validate_sync(account.get("sync", DEFAULT_SYNC))
    validated["safety"] = _validate_safety(account.get("safety", DEFAULT_SAFETY))
    validated["runtime"] = _validate_runtime(account.get("runtime", DEFAULT_RUNTIME))
    validated["id"] = account_fingerprint(validated)
    return validated


def _refresh_legacy_view(
    data: dict[str, Any], active_id: str | None = None
) -> dict[str, Any]:
    accounts = data.get("accounts", [])
    first = None
    if active_id:
        first = next((a for a in accounts if a.get("id") == active_id), None)
    if first is None and accounts:
        first = accounts[0]
    if first:
        data["account"] = {
            "id": first["id"],
            "server_url": first["server_url"],
            "login_name": first["login_name"],
            "authentication_type": first["authentication_type"],
            "local_root": first["local_root"],
            "remote_path": first["remote_path"],
        }
        data["sync"] = first["sync"]
        data["safety"] = first["safety"]
        data["runtime"] = first["runtime"]
    else:
        data["account"] = None
        data["sync"] = data.get("sync") or _deep_merge(DEFAULT_SYNC, {})
        data["safety"] = data.get("safety") or _deep_merge(DEFAULT_SAFETY, {})
        data["runtime"] = data.get("runtime") or _deep_merge(DEFAULT_RUNTIME, {})
    return data


def validate_config(
    data: dict[str, Any], active_id: str | None = None
) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ConfigurationError("Configuration root must be an object.")
    version = data.get("schema_version", 1)
    if version > SCHEMA_VERSION:
        raise ConfigurationError(
            f"Configuration schema {version} is newer than this application supports."
        )
    merged = _deep_merge(DEFAULT_CONFIG, _migrate_to_v3(data))
    merged["schema_version"] = SCHEMA_VERSION

    accounts: list[dict[str, Any]] = []
    for account in merged.get("accounts", []):
        accounts.append(_validate_account(account))
    merged["accounts"] = accounts

    logging_config = merged["logging"]
    try:
        retention_days = int(logging_config["retention_days"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ConfigurationError("Invalid setting: retention_days") from exc
    if not 1 <= retention_days <= 365:
        raise ConfigurationError("retention_days must be between 1 and 365.")
    logging_config["retention_days"] = retention_days
    logging_config["save_logs"] = bool(logging_config.get("save_logs", True))

    proxy = merged["network"].get("custom_proxy")
    if proxy:
        parsed_proxy = urlsplit(str(proxy))
        if (
            parsed_proxy.scheme.lower() not in {"http", "https"}
            or not parsed_proxy.netloc
            or parsed_proxy.username
            or parsed_proxy.password
        ):
            raise ConfigurationError(
                "The custom proxy must be an HTTP(S) URL without embedded credentials."
            )
    return _refresh_legacy_view(merged, active_id)


class ConfigStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (config_dir() / "settings.json")
        self.data = copy.deepcopy(DEFAULT_CONFIG)
        self._active_view_id: str | None = None
        self._listeners: list[Callable[[dict[str, Any]], None]] = []

    @property
    def configured(self) -> bool:
        return bool(self.data.get("accounts"))

    @property
    def accounts(self) -> list[dict[str, Any]]:
        return self.data.get("accounts", [])

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            self.data = validate_config(copy.deepcopy(DEFAULT_CONFIG))
            return self.data
        try:
            parsed = json.loads(self.path.read_text(encoding="utf-8"))
            self.data = validate_config(parsed)
        except (OSError, json.JSONDecodeError, ConfigurationError) as exc:
            raise ConfigurationError(f"Could not load {self.path}: {exc}") from exc
        return self.data

    def _payload(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "accounts": copy.deepcopy(self.data.get("accounts", [])),
            "general": copy.deepcopy(self.data.get("general", {})),
            "logging": copy.deepcopy(self.data.get("logging", {})),
            "network": copy.deepcopy(self.data.get("network", {})),
        }

    def save(self, *, notify: bool = True) -> None:
        payload = self._payload()
        self.data = validate_config(payload, active_id=self._active_view_id)
        ensure_private_directory(self.path.parent)
        temporary = self.path.with_suffix(".tmp")
        content = json.dumps(self.data, indent=2, ensure_ascii=False) + "\n"
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            temporary.replace(self.path)
        finally:
            if temporary.exists():
                temporary.unlink(missing_ok=True)
        if notify:
            for listener in tuple(self._listeners):
                listener(self.data)

    def subscribe(self, callback: Callable[[dict[str, Any]], None]) -> Callable[[], None]:
        self._listeners.append(callback)

        def unsubscribe() -> None:
            if callback in self._listeners:
                self._listeners.remove(callback)

        return unsubscribe

    def add_account(self, account: dict[str, Any]) -> str:
        validated = _validate_account(account)
        accounts = list(self.data.get("accounts", []))
        if any(item.get("id") == validated["id"] for item in accounts):
            raise ConfigurationError(
                "An account with the same server, username, local folder and "
                "remote path already exists."
            )
        accounts.append(validated)
        self.data["accounts"] = accounts
        self._active_view_id = validated["id"]
        self.save()
        return validated["id"]

    def remove_account(self, account_id: str) -> bool:
        accounts = [
            item for item in self.data.get("accounts", []) if item.get("id") != account_id
        ]
        if len(accounts) == len(self.data.get("accounts", [])):
            return False
        self.data["accounts"] = accounts
        if self._active_view_id == account_id:
            self._active_view_id = accounts[0]["id"] if accounts else None
        self.save()
        return True

    def set_active_view(self, account_id: str | None) -> None:
        self._active_view_id = account_id
        self.data = _refresh_legacy_view(self.data, account_id)

    def reset_account(self) -> None:
        self._active_view_id = None
        self.data = validate_config(copy.deepcopy(DEFAULT_CONFIG))
        self.save()
