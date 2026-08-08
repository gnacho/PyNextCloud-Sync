from __future__ import annotations

import datetime as dt
from typing import Any, Callable

from gi.repository import GLib

from pynextcloud_sync.core.exclusions import ExclusionMatcher
from pynextcloud_sync.core.state import AppState, StateController
from pynextcloud_sync.core.triggers import CoalescingQueue, Trigger, manual_only
from pynextcloud_sync.nextcloud.command import NextcloudCmdMissingError, build_command
from pynextcloud_sync.nextcloud.credentials import KeyringLockedError
from pynextcloud_sync.util.paths import config_dir
from pynextcloud_sync.util.i18n import _

from .sync_engine import SyncEngine, SyncResult


class SyncScheduler:
    DEBOUNCE_MS = 2000
    COOLDOWN_SECONDS = 4

    def __init__(
        self,
        config: Any,
        credentials: Any,
        engine: SyncEngine,
        state: StateController,
        logger: Any,
        on_completed: Callable[[SyncResult], None] | None = None,
    ) -> None:
        self.config = config
        self.credentials = credentials
        self.engine = engine
        self.state = state
        self.logger = logger
        self.on_completed = on_completed
        self.queue = CoalescingQueue()
        self.online = True
        self.user_paused = False
        self.battery_paused = False
        self.local_dirty = False
        self.remote_pending = False
        self._debounce_source = 0
        self._start_source = 0
        self._cooldown_source = 0
        self._preparing = False
        self._stopped = False
        self._feedback_followup_pending = False
        self._inotify_during_sync = False

    @property
    def paused(self) -> bool:
        return self.user_paused or self.battery_paused

    @property
    def manual_only(self) -> bool:
        return manual_only(self.config.data["sync"])

    def request(self, trigger: Trigger) -> None:
        if self._stopped:
            return
        if self.engine.running or self._preparing:
            if trigger == Trigger.LOCAL_INOTIFY:
                self._inotify_during_sync = True
            self.queue.add(trigger)
            self.logger.info("Synchronization request coalesced: %s", trigger.value)
            return
        if self.paused and trigger != Trigger.MANUAL:
            if trigger in {Trigger.LOCAL_INOTIFY, Trigger.LOCAL_INTERVAL}:
                self.local_dirty = True
            else:
                self.remote_pending = True
            self.logger.info("Synchronization deferred while paused: %s", trigger.value)
            return
        if not self.online:
            self.queue.add(trigger)
            self.state.set(AppState.OFFLINE, _("Waiting for a network connection"))
            self.logger.info("Synchronization deferred while offline: %s", trigger.value)
            return
        self.queue.add(trigger)
        if trigger == Trigger.LOCAL_INOTIFY:
            self._schedule_debounce()
        else:
            self._schedule_start()

    def _schedule_debounce(self) -> None:
        if self._debounce_source:
            GLib.source_remove(self._debounce_source)
        self.state.set(AppState.SYNC_QUEUED, _("Waiting for local changes to settle"))
        self._debounce_source = GLib.timeout_add(self.DEBOUNCE_MS, self._debounce_elapsed)

    def _debounce_elapsed(self) -> bool:
        self._debounce_source = 0
        self._schedule_start()
        return GLib.SOURCE_REMOVE

    def _schedule_start(self) -> None:
        if (
            self._stopped
            or self._debounce_source
            or self._start_source
            or self._cooldown_source
            or self._preparing
            or self.engine.running
        ):
            return
        self.state.set(AppState.SYNC_QUEUED, _("Synchronization scheduled"))
        self._start_source = GLib.idle_add(self._start)

    def _start(self) -> bool:
        self._start_source = 0
        if self._stopped or self._preparing or self.engine.running or not self.queue or not self.online:
            return GLib.SOURCE_REMOVE
        reasons = self.queue.take()
        if self.paused and Trigger.MANUAL not in reasons:
            self.local_dirty = True
            return GLib.SOURCE_REMOVE
        account = self.config.data.get("account")
        if not account:
            self.state.set(AppState.UNCONFIGURED)
            return GLib.SOURCE_REMOVE
        self.state.set(AppState.SYNCING, _("Synchronizing files…"))
        reason_text = ", ".join(sorted(reason.value for reason in reasons))
        self.logger.info("Synchronization triggers: %s", reason_text)
        self._preparing = True

        def secret_ready(password: str | None, error: Exception | None) -> None:
            if self._stopped:
                return
            self._preparing = False
            if error:
                if isinstance(error, KeyringLockedError):
                    self.state.set(AppState.KEYRING_LOCKED, _("Password keyring is locked"))
                else:
                    self.state.set(AppState.AUTH_REQUIRED, _("Could not read the account credential"))
                self.logger.error("Credential lookup failed: %s", error)
                return
            if not password:
                self.state.set(AppState.AUTH_REQUIRED, _("No stored credential was found"))
                return
            self.logger.add_secret(password)
            sync = self.config.data["sync"]
            matcher = ExclusionMatcher(
                sync.get("exclude_patterns", []), sync.get("exclude_patterns_enabled", True)
            )
            exclude_path = matcher.write_nextcloudcmd_file(config_dir() / "excludes.lst")
            try:
                spec = build_command(
                    account,
                    sync,
                    self.config.data["network"],
                    password,
                    exclude_path,
                )
            except NextcloudCmdMissingError as exc:
                self.state.set(AppState.ERROR, str(exc))
                self.logger.error(exc)
                return
            feedback_followup = self._feedback_followup_pending
            self._feedback_followup_pending = False
            self.engine.run(
                spec,
                lambda result: self._finished(result, reasons, feedback_followup),
            )

        self.credentials.lookup(account["server_url"], account["login_name"], secret_ready)
        return GLib.SOURCE_REMOVE

    def _finished(
        self,
        result: SyncResult,
        reasons: set[Trigger],
        feedback_followup: bool = False,
    ) -> None:
        if self._stopped:
            return
        self.config.data["runtime"]["last_exit_code"] = result.exit_code
        self.logger.info("nextcloudcmd exited with code %s after %.1f seconds.", result.exit_code, result.duration)
        if result.successful:
            self.config.data["runtime"]["last_successful_sync"] = dt.datetime.now(
                dt.timezone.utc
            ).isoformat()
            if result.classification == "conflict":
                self.state.set(AppState.IDLE_OK, _("Synchronized with conflicts — review the log"))
            else:
                self._set_idle_state()
            self.logger.info("Synchronization completed successfully.")
        elif result.classification == "authentication":
            self.state.set(AppState.AUTH_REQUIRED, _("Your Nextcloud account needs attention"))
            self.logger.error("Synchronization failed because authentication was rejected.")
        else:
            self.state.set(AppState.ERROR, _("Synchronization failed — view the log"))
            self.logger.error("Synchronization failed with exit code %s.", result.exit_code)
        try:
            self.config.save(notify=False)
        except Exception as exc:
            self.logger.error("Could not save runtime state: %s", exc)
        if self.on_completed:
            self.on_completed(result)

        queued = bool(self.queue)
        if self._inotify_during_sync:
            if feedback_followup:
                # Suppress only the local feedback from the reconciliation itself.
                # Manual, remote, resume, and network triggers must remain queued.
                self.queue.discard(Trigger.LOCAL_INOTIFY)
            else:
                self._feedback_followup_pending = True
                self.queue.add(Trigger.LOCAL_INOTIFY)
            queued = bool(self.queue)
        self._inotify_during_sync = False
        self._cooldown_source = GLib.timeout_add_seconds(
            self.COOLDOWN_SECONDS, self._cooldown_finished, queued
        )

    def _cooldown_finished(self, run_pending: bool) -> bool:
        self._cooldown_source = 0
        if self._stopped:
            return GLib.SOURCE_REMOVE
        if run_pending and self.queue and self.online and not self.paused:
            self._schedule_start()
        else:
            if not self.paused:
                self._set_idle_state()
        return GLib.SOURCE_REMOVE

    def set_user_paused(self, paused: bool) -> None:
        self.user_paused = paused
        if paused:
            self.state.set(AppState.PAUSED_USER, _("Synchronization is paused"))
        else:
            should_reconcile = self.local_dirty or self.remote_pending or bool(self.queue)
            self.local_dirty = self.remote_pending = False
            if should_reconcile and not self.manual_only:
                self.request(Trigger.RESUME)
            else:
                self._set_idle_state()

    def set_battery_paused(self, paused: bool) -> None:
        was_paused = self.battery_paused
        self.battery_paused = paused
        if paused:
            message = _("Will pause after the current synchronization") if self.engine.running else _("Paused on battery")
            self.state.set(AppState.PAUSED_BATTERY, message)
        elif was_paused and not self.user_paused:
            should_reconcile = self.local_dirty or self.remote_pending or bool(self.queue)
            self.local_dirty = self.remote_pending = False
            if should_reconcile and not self.manual_only:
                self.request(Trigger.RESUME)
            else:
                self._set_idle_state()

    def set_online(self, online: bool) -> None:
        was_online = self.online
        self.online = online
        if not online:
            self.state.set(AppState.OFFLINE, _("Waiting for a network connection"))
        elif not was_online:
            if self.queue or not self.manual_only:
                self.request(Trigger.NETWORK_RESTORED)
            else:
                self._set_idle_state()

    def _set_idle_state(self) -> None:
        if self.user_paused:
            self.state.set(AppState.PAUSED_USER, _("Synchronization is paused"))
        elif self.battery_paused:
            self.state.set(AppState.PAUSED_BATTERY, _("Paused on battery"))
        elif not self.online:
            self.state.set(AppState.OFFLINE, _("Waiting for a network connection"))
        elif self.manual_only:
            self.state.set(AppState.IDLE_MANUAL_ONLY, _("Automatic synchronization is off"))
        else:
            self.state.set(AppState.IDLE_OK, _("Synchronized"))

    def stop(self) -> None:
        self._stopped = True
        for attribute in ("_debounce_source", "_start_source", "_cooldown_source"):
            source = getattr(self, attribute)
            if source:
                GLib.source_remove(source)
                setattr(self, attribute, 0)
        self.queue.clear()
        self.local_dirty = False
        self.remote_pending = False
        self._feedback_followup_pending = False
        if self.engine.running:
            self.engine.cancel()
