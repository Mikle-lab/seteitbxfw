import tempfile
import unittest

from collector.analytics.alert_context import present, wallet_contexts
from collector.storage import Store, write


class AlertContextTests(unittest.TestCase):
    def test_aligns_balances_and_flows_on_the_same_utc_boundary(self):
        with tempfile.TemporaryDirectory() as temp:
            store = Store(temp)
            write(store.state, {"wallets": {"A": {"balance": "1100000", "updated": "2026-11-27T09:00:00Z"}},
                                "payment_history": {"A": {"complete": True, "through": "2026-10-28",
                                    "end": "2026-11-27", "days": {"2026-11-26": [10000, 3000, 2]}}}})
            for day, balance in (("2026-11-19", "1000000"), ("2026-11-26", "1090000")):
                write(store.root / "archive" / f"{day}.json",
                      {"snapshots": {"a": {"address": "A", "time": day + "T23:00:00Z", "balance": balance}}})
            result = present(wallet_contexts(store.root, {"A"}, "2026-11-27T09:00:00Z")["A"])
            self.assertIn("Последний баланс: 1 100 000,00 XLM", result)
            self.assertIn("7 дн. · было 1 000 000,00 → стало 1 090 000,00", result)
            self.assertIn("30 дн. · для сравнения баланса не хватает снимков", result)
            self.assertIn("итог +0,0007000", result)

    def test_incomplete_window_does_not_show_zero_flow(self):
        context = dict(balance="1", updated="2026-11-27T00:00:00Z", end="2026-11-27",
                       periods={7: dict(before=None, after=None, flows=dict(complete=False))})
        text = present(context)
        self.assertIn("история за период неполная", text)
        self.assertNotIn("получено 0", text)
