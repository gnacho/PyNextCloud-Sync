from __future__ import annotations

import unittest

from nextsync.core.state import (
    AggregateStateController,
    AppState,
    StateController,
)
from nextsync.nextcloud.nextcloudcmd_progress import SyncProgress


class AggregateStateControllerTests(unittest.TestCase):
    def test_empty_aggregate_is_unconfigured(self) -> None:
        aggregate = AggregateStateController()
        self.assertEqual(aggregate.snapshot.state, AppState.UNCONFIGURED)

    def test_worst_state_wins_across_controllers(self) -> None:
        first = StateController(AppState.IDLE_OK)
        second = StateController(AppState.OFFLINE)
        third = StateController(AppState.SYNCING)
        aggregate = AggregateStateController([first, second])
        self.assertEqual(aggregate.snapshot.state, AppState.OFFLINE)
        aggregate.add(third)
        self.assertEqual(aggregate.snapshot.state, AppState.OFFLINE)
        second.set(AppState.ERROR)
        self.assertEqual(aggregate.snapshot.state, AppState.ERROR)

    def test_removing_a_controller_recomputes(self) -> None:
        first = StateController(AppState.IDLE_OK)
        second = StateController(AppState.ERROR)
        aggregate = AggregateStateController([first, second])
        self.assertEqual(aggregate.snapshot.state, AppState.ERROR)
        aggregate.remove(second)
        self.assertEqual(aggregate.snapshot.state, AppState.IDLE_OK)

    def test_clear_resets_to_unconfigured(self) -> None:
        first = StateController(AppState.ERROR)
        aggregate = AggregateStateController([first])
        aggregate.clear()
        self.assertEqual(aggregate.snapshot.state, AppState.UNCONFIGURED)

    def test_subscribers_are_notified_on_changes(self) -> None:
        first = StateController(AppState.IDLE_OK)
        aggregate = AggregateStateController([first])
        seen: list[object] = []
        aggregate.subscribe(lambda snapshot: seen.append(snapshot.state))
        first.set(AppState.SYNCING)
        self.assertEqual(seen[-1], AppState.SYNCING)

    def test_idle_ok_outranks_unconfigured(self) -> None:
        configured = StateController(AppState.IDLE_OK)
        fresh = StateController(AppState.UNCONFIGURED)
        aggregate = AggregateStateController([configured, fresh])
        self.assertEqual(aggregate.snapshot.state, AppState.IDLE_OK)

    def test_progress_updates_and_subscribers_are_notified(self) -> None:
        controller = StateController(AppState.IDLE_OK)
        seen: list[SyncProgress | None] = []
        unsubscribe = controller.subscribe_progress(lambda progress: seen.append(progress))
        self.assertEqual(seen, [None])
        progress = SyncProgress("download", "/tmp/a.pdf", 1)
        controller.set_progress(progress)
        self.assertEqual(seen[-1], progress)
        controller.set_progress(None)
        self.assertEqual(seen[-1], None)
        unsubscribe()
        controller.set_progress(SyncProgress("upload", "/tmp/b", 2))
        self.assertEqual(len(seen), 3)

    def test_duplicate_progress_is_not_resent(self) -> None:
        controller = StateController(AppState.IDLE_OK)
        seen: list[SyncProgress | None] = []
        controller.subscribe_progress(lambda progress: seen.append(progress))
        progress = SyncProgress("download", "/tmp/a.pdf", 1)
        controller.set_progress(progress)
        controller.set_progress(progress)
        self.assertEqual(len(seen), 2)


if __name__ == "__main__":
    unittest.main()
