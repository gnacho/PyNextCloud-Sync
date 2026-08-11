from __future__ import annotations

import unittest

from pynextcloud_sync.core.debounce import DebounceGate


class FakeGLib:
    SOURCE_REMOVE = False
    SOURCE_CONTINUE = True
    callbacks: dict[int, object] = {}
    next_id = 1

    @classmethod
    def _add(cls, callback: object) -> int:
        source_id = cls.next_id
        cls.next_id += 1
        cls.callbacks[source_id] = callback
        return source_id

    @classmethod
    def timeout_add(cls, _milliseconds: int, callback: object, *args: object) -> int:
        return cls._add(lambda: callback(*args))

    @classmethod
    def timeout_add_seconds(cls, _seconds: int, callback: object, *args: object) -> int:
        return cls._add(lambda: callback(*args))

    @classmethod
    def source_remove(cls, source_id: int) -> None:
        cls.callbacks.pop(source_id, None)


class DebounceGateTests(unittest.TestCase):
    def setUp(self) -> None:
        FakeGLib.callbacks = {}
        FakeGLib.next_id = 1

    def _gate(self, on_ready: object = lambda: None) -> DebounceGate:
        gate = DebounceGate(
            debounce_ms=2000,
            cooldown_seconds=4,
            on_ready=on_ready,
            glib=FakeGLib,
        )
        return gate

    def test_restarting_debounce_cancels_the_previous_timer(self) -> None:
        gate = self._gate()
        gate.kick()
        first = gate.debounce_source
        self.assertNotEqual(first, 0)
        gate.kick()
        self.assertNotEqual(gate.debounce_source, first)
        self.assertNotIn(first, FakeGLib.callbacks)

    def test_debounce_elapsed_triggers_ready(self) -> None:
        fired: list[bool] = []
        gate = self._gate(on_ready=lambda: fired.append(True))
        gate.kick()
        self.assertTrue(callable(FakeGLib.callbacks[gate.debounce_source]))
        FakeGLib.callbacks[gate.debounce_source]()
        self.assertEqual(fired, [True])
        self.assertEqual(gate.debounce_source, 0)

    def test_cooldown_locks_until_it_expires(self) -> None:
        gate = self._gate()
        gate.begin_cooldown()
        self.assertTrue(gate.in_cooldown)
        FakeGLib.callbacks[gate.cooldown_source]()
        self.assertFalse(gate.in_cooldown)
        self.assertEqual(gate.cooldown_source, 0)

    def test_cooldown_runs_its_finished_callback(self) -> None:
        fired: list[bool] = []
        gate = self._gate()
        gate.begin_cooldown(lambda: fired.append(True))
        FakeGLib.callbacks[gate.cooldown_source]()
        self.assertEqual(fired, [True])

    def test_stop_cancels_both_sources(self) -> None:
        gate = self._gate()
        gate.kick()
        gate.begin_cooldown()
        gate.stop()
        self.assertEqual(gate.debounce_source, 0)
        self.assertEqual(gate.cooldown_source, 0)
        self.assertFalse(FakeGLib.callbacks)


if __name__ == "__main__":
    unittest.main()
