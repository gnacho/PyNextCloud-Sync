from __future__ import annotations

import unittest

from nextsync.core.sync_permit import SyncPermit


class SyncPermitTests(unittest.TestCase):
    def test_single_permit_is_acquired_and_released(self) -> None:
        permit = SyncPermit()
        self.assertTrue(permit.available)
        self.assertTrue(permit.try_acquire())
        self.assertFalse(permit.available)
        self.assertFalse(permit.try_acquire())
        permit.release()
        self.assertTrue(permit.available)

    def test_release_wakes_one_waiter_in_fifo_order(self) -> None:
        permit = SyncPermit()
        fired: list[int] = []
        permit.try_acquire()
        permit.wait_for_release(lambda: fired.append(1))
        permit.wait_for_release(lambda: fired.append(2))
        permit.release()
        self.assertEqual(fired, [1])
        permit.try_acquire()
        permit.release()
        self.assertEqual(fired, [1, 2])

    def test_max_concurrent_limits_parallel_runs(self) -> None:
        permit = SyncPermit(max_concurrent=2)
        self.assertTrue(permit.try_acquire())
        self.assertTrue(permit.try_acquire())
        self.assertFalse(permit.try_acquire())
        permit.release()
        self.assertTrue(permit.try_acquire())

    def test_rejects_zero_max_concurrent(self) -> None:
        with self.assertRaises(ValueError):
            SyncPermit(max_concurrent=0)


if __name__ == "__main__":
    unittest.main()
