from collections import defaultdict
from datetime import date, timedelta
import tempfile
import unittest

from collector.analytics.trends import anomaly_for_day, build_trends, closed_day_signals, daily_changes, trend
from collector.model import stroops, xlm
from collector.storage import Store, write
from test_collector import RECIPIENT


def close(day, amount, hour="23:55:00"):
    return dict(id=str(day), address=RECIPIENT, time=f"{day}T{hour}Z", balance=xlm(amount))


class TrendsTests(unittest.TestCase):
    def test_daily_coverage_and_previous_observation(self):
        samples = [
            close("2026-11-13", 100),
            close("2026-11-14", 110, "12:00:00"),
            dict(close("2026-11-15", 130, "00:05:00"), previous_time="2026-11-14T23:55:00Z", delta=xlm(20)),
            close("2026-11-17", 165),
        ]
        self.assertEqual(daily_changes(samples), {date(2026, 11, 14): 10})
        stats = trend(daily_changes(samples), date(2026, 11, 18), 7)
        self.assertEqual(stats["observed"], 1)
        self.assertEqual(stats["net"], "0.0000010")
        self.assertIsNone(trend({}, date(2026, 11, 18), 7)["net"])

    def test_seven_day_ranking_includes_only_complete_wallets(self):
        today = date(2026, 11, 19)
        samples = [close(today - timedelta(days=8 - index), 100 + index * 3) for index in range(8)]
        periods, wallets = build_trends({RECIPIENT: dict(category="whale")}, defaultdict(list, {RECIPIENT: samples}), today)
        self.assertEqual(periods["7d"]["complete"], 1)
        self.assertEqual(periods["7d"]["accumulation"][0]["net"], "0.0000021")
        self.assertEqual(periods["30d"]["complete"], 0)
        self.assertEqual(wallets[RECIPIENT]["30d"]["observed"], 7)

    def test_outlier_needs_a_baseline_and_detects_negative_move(self):
        target = date(2026, 11, 19)
        minimum = stroops("25000")
        changes = {target - timedelta(days=n): stroops("1000") for n in range(1, 8)}
        self.assertIsNone(anomaly_for_day(RECIPIENT, changes, target, minimum))
        changes[target] = -stroops("150000")
        signal = anomaly_for_day(RECIPIENT, changes, target, minimum)
        self.assertEqual((signal["kind"], signal["level"], signal["amount"]), ("daily_outlier", "high", "-150000.0000000"))
        self.assertIsNone(anomaly_for_day(RECIPIENT, {target: changes[target]}, target, minimum))

    def test_anomaly_reuses_archives_and_advances_its_own_day_checkpoint(self):
        target = date(2026, 11, 19)
        initial = stroops("1000000")
        with tempfile.TemporaryDirectory() as directory:
            store = Store(directory)
            for offset in range(8, -1, -1):
                day = target - timedelta(days=offset)
                row = close(day, initial if offset else initial + stroops("75000"))
                write(store.root / "archive" / f"{day}.json", {"snapshots": {row["id"]: row}})
            state = {"wallets": {RECIPIENT: {}}}
            self.assertEqual(closed_day_signals(state, store, [], "2026-11-20T02:55:00Z", stroops("25000")), [])
            signals = closed_day_signals(state, store, [], "2026-11-20T03:05:00Z", stroops("25000"))
            self.assertEqual(len(signals), 1)
            self.assertEqual(state["trends_evaluated_through"], "2026-11-19")
            self.assertEqual(closed_day_signals(state, store, [], "2026-11-20T03:11:00Z", stroops("25000")), [])
