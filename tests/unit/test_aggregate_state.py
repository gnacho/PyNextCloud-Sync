from __future__ import annotations

import unittest

from pynextcloud_sync.core.state import (
    AggregateStateController,
    AppState,
    StateController,
)


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
        second = StateController(AppState.SAFETY_REVIEW)
        aggregate = AggregateStateController([first, second])
        self.assertEqual(aggregate.snapshot.state, AppState.SAFETY_REVIEW)
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


if __name__ == "__main__":
    unittest.main()
