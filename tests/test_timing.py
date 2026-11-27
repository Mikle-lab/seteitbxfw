from datetime import datetime
import unittest

from collector.freshness import fresh
from collector.timing import next_slot


class TimingTests(unittest.TestCase):
    def test_slots_stay_on_the_initial_clock(self):
        self.assertEqual(next_slot(1800, 1820), 2160)
        self.assertEqual(next_slot(1800, 2160), 2520)
        self.assertEqual(next_slot(1800, 2570), 2880)
        with self.assertRaises(ValueError):
            next_slot(3200, 1800)

    def test_lagged_scan_only_counts_as_fresh_when_its_cursor_is_fresh(self):
        now = datetime.fromisoformat("2026-11-27T15:09:00Z")
        state = dict(last_success="2026-11-27T15:08:00Z", caught_up=False,
                     last_operation="2026-11-27T14:54:00Z")
        self.assertFalse(fresh(state, now, 4))
        self.assertTrue(fresh(dict(state, caught_up=True), now, 4))
