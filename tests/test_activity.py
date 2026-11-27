import unittest

from collector.analytics.activity import direct_interactions, inactivity, observe_activity


class ActivityTests(unittest.TestCase):
    first = "2026-10-01T09:00:00Z"

    def test_inactivity_is_bounded_by_observation_start_and_stream(self):
        wallet = {"first_seen": self.first, "last_activity": "2026-09-01T00:00:00Z"}
        self.assertIsNone(inactivity(wallet, "2026-09-30T00:00:00Z", 30))
        active = inactivity(wallet, "2026-10-31T08:59:59Z", 30)
        dormant = inactivity(wallet, "2026-10-31T09:00:00Z", 30)
        self.assertEqual((active["days"], active["dormant"]), (29, False))
        self.assertEqual((dormant["days"], dormant["dormant"]), (30, True))

    def test_activity_resumption_emits_once_and_preserves_latest_time(self):
        wallet = {"first_seen": self.first, "last_activity": self.first}
        when = "2026-11-02T12:00:00Z"
        signal = observe_activity(wallet, "A", when, "42", 30)
        self.assertEqual(signal["id"], "42:A:resumed")
        self.assertEqual(signal["kind"], "activity_resumed")
        self.assertIsNone(observe_activity(wallet, "A", when, "43", 30))
        self.assertIsNone(observe_activity(wallet, "A", self.first, "40", 30))
        self.assertEqual(wallet["last_activity"], when)

    def test_labeled_account_activity_has_no_reactivation_alert(self):
        wallet = {"first_seen": self.first, "label": {"type": "exchange"}}
        when = "2026-11-03T12:00:00Z"
        self.assertIsNone(observe_activity(wallet, "B", when, "44", 30))
        self.assertEqual(wallet["last_activity"], when)

    def test_direct_interactions_require_distinct_transactions_and_days(self):
        def operation(number, day, hash_, sender="A", recipient="B", kind="payment"):
            return dict(id=str(number), time=f"2026-11-{day:02d}T12:00:00Z", amount="100000.0000001",
                        sender=sender, recipient=recipient, kind=kind, hash=hash_)

        rows = [
            operation(1, 1, "tx1"), operation(2, 1, "tx1", "B", "A"),
            operation(3, 2, "tx2"), operation(4, 2, "tx3", "B", "A"),
            operation(5, 2, "pool", kind="path_receive"), operation(6, 2, "exchange", recipient="C"),
        ]
        wallets = {"A": {}, "B": {}, "C": {"label": {"type": "exchange"}}}
        self.assertEqual(direct_interactions(rows[:3], wallets, self.first), [])
        result = direct_interactions(rows, wallets, self.first)
        self.assertEqual(len(result), 1)
        pair = result[0]
        self.assertEqual((pair["left"], pair["right"], pair["transactions"], pair["days"]), ("A", "B", 3, 2))
        self.assertEqual(pair["amount"], "400000.0000004")
        self.assertEqual(len(pair["examples"]), 3)
        self.assertEqual(direct_interactions(rows, wallets, "2026-11-02T00:00:00Z"), [])
