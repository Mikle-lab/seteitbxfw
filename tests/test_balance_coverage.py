from datetime import datetime, timedelta
import unittest

from collector.analytics.balance_coverage import private_balance_periods
from collector.export import PERIODS
from test_collector import RECIPIENT, SENDER, key

END = datetime.fromisoformat("2026-11-27T12:00:00Z")
START = END - timedelta(days=1)
APPROVED = {"status": "approved", "source": "fixture", "reason": "reviewed"}
SDF_HOT_3 = "GAPV2C4BTHXPL2IVYDXJ5PUU7Q3LAXU7OAQDP7KVYHLCNM2JTAJNOQQI"


def row(at, balance, **extra):
    return {"time": at.isoformat(), "balance": str(balance), **extra}


def calculate(registry, snapshots, wallets=None, labels=None):
    return private_balance_periods({"private_review": registry, "labels": labels or {}},
                                   wallets or {}, snapshots, END, PERIODS)


class BalanceCoverageTests(unittest.TestCase):
    def test_no_approved_holders_is_not_a_measured_zero(self):
        periods = calculate({}, {RECIPIENT: [row(START, 100), row(END, 110)]})
        self.assertEqual(set(periods), set(PERIODS))
        for result in periods.values():
            self.assertEqual((result["status"], result["approved"], result["measured"]),
                             ("no_holders", 0, 0))
            self.assertIsNone(result["net"])

    def test_does_not_infer_private_holders_without_a_registry(self):
        periods = private_balance_periods({"labels": {}}, {},
                                            {RECIPIENT: [row(START, 100), row(END, 110)]}, END, PERIODS)
        self.assertEqual(periods["24h"]["status"], "no_holders")

    def test_first_observation_or_a_stale_measurement_is_insufficient(self):
        for points in ([row(START, 100)], [row(END, 110)],
                       [row(START + timedelta(seconds=1), 100), row(END, 110)],
                       [row(START - timedelta(hours=3, seconds=1), 100), row(END, 110)],
                       [row(START, 100), row(END - timedelta(hours=3, seconds=1), 110)]):
            with self.subTest(points=points):
                result = calculate({RECIPIENT: APPROVED}, {RECIPIENT: points})["24h"]
                self.assertEqual(result["status"], "insufficient")
                self.assertIsNone(result["net"])
                self.assertIsNone(result["observed_through"])

    def test_partial_uses_the_same_measured_addresses_and_records_coverage(self):
        last = END - timedelta(minutes=20)
        result = calculate({RECIPIENT: APPROVED, SENDER: APPROVED},
                           {RECIPIENT: [row(START, 100), row(last, 110)],
                            SENDER: [row(END, 5000)]})["24h"]
        self.assertEqual((result["status"], result["approved"], result["measured"]), ("partial", 2, 1))
        self.assertEqual((result["net"], result["increased"], result["decreased"]), ("10.0000000", 1, 0))
        self.assertEqual(result["observed_through"], "2026-11-27T11:40:00Z")

    def test_compensating_changes_and_unchanged_balance_are_measured(self):
        unchanged = key(3)
        result = calculate(dict.fromkeys((SENDER, RECIPIENT, unchanged), APPROVED), {
            SENDER: [row(START, 100), row(END, 90)],
            RECIPIENT: [row(START, 100), row(END, 110)],
            unchanged: [row(START, 0), row(END, 0)],
        })["24h"]
        self.assertEqual((result["status"], result["net"], result["increased"], result["decreased"]),
                         ("complete", "0.0000000", 1, 1))
        self.assertEqual(result["measured"], 3)

    def test_previous_snapshot_and_current_unchanged_lookup_are_real_measurements(self):
        points = [row(START + timedelta(hours=1), 101, previous_time=START.isoformat(), delta="1")]
        result = calculate({RECIPIENT: APPROVED}, {RECIPIENT: points},
                           {RECIPIENT: {"updated": END.isoformat(), "balance": "101"}})["24h"]
        self.assertEqual((result["status"], result["net"]), ("complete", "1.0000000"))

    def test_excludes_service_exchange_and_candidates_even_with_large_balances(self):
        registry = {RECIPIENT: APPROVED, SENDER: APPROVED,
                    SDF_HOT_3: {"status": "service", "source": "fixture", "reason": "SDF"}}
        addresses = (RECIPIENT, SENDER, SDF_HOT_3, key(4))
        result = calculate(registry, {address: [row(START, 1_000_000), row(END, 2_000_000)] for address in addresses},
                           labels={SENDER: {"type": "exchange"}})["24h"]
        self.assertEqual((result["approved"], result["measured"], result["net"]),
                         (1, 1, "1000000.0000000"))

    def test_short_windows_use_tighter_tolerance_and_all_starts_at_first_snapshot(self):
        first = END - timedelta(minutes=90)
        points = [row(first, 11), row(END, 21)]
        periods = calculate({RECIPIENT: APPROVED}, {RECIPIENT: points})
        self.assertEqual((periods["1h"]["status"], periods["1h"]["max_sample_age_seconds"]), ("complete", 1800))
        self.assertEqual(periods["all"]["window_start"], "2026-11-27T10:30:00Z")
        self.assertEqual(periods["all"]["net"], "10.0000000")
