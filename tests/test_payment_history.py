import unittest

from collector.analytics.payment_history import payment_page, summarize_history
from collector.analytics.review import private_payment, private_signal, status


class PaymentHistoryTests(unittest.TestCase):
    def test_descending_pages_mark_only_finished_days_complete(self):
        def payment(token, day, sender="B", target="A", kind="payment"):
            return {"paging_token": str(token), "created_at": day + "T12:00:00Z", "from": sender, "to": target,
                    "asset_type": "native", "type": kind, "amount": "5.1234567"}

        class Api:
            payment_page_size = 2

            def payments(self, address, cursor):
                return {None: [payment(7, "2026-11-27"), payment(6, "2026-11-26")],
                        "6": [payment(6, "2026-11-26"), payment(5, "2026-11-26", "A", "B")],
                        "5": [payment(3, "2026-11-25", kind="path_payment_strict_send")]}[cursor]

        task = dict(start="2026-10-28", end="2026-11-27", days={})
        api = Api()
        payment_page(api, "A", task, "2025-01-01")
        self.assertFalse(summarize_history(task)["periods"]["1"]["complete"])
        payment_page(api, "A", task, "2025-01-01")
        payment_page(api, "A", task, "2025-01-01")
        stats = summarize_history(task)["periods"]["30"]
        self.assertEqual((stats["payments"], stats["net"], stats["complete"]), (2, "0.0000000", True))

    def test_distinguishes_absent_history_from_zero_payment(self):
        class Api:
            payment_page_size = 200
            def payments(self, address, cursor):
                return []

        task = dict(start="2026-10-28", end="2026-11-27", days={})
        payment_page(Api(), "A", task, "2026-11-21")
        periods = summarize_history(task)["periods"]
        self.assertTrue(periods["1"]["complete"])
        self.assertFalse(periods["30"]["complete"])

    def test_quarantines_unknowns_and_excludes_technical_notifications(self):
        approved = {"status": "approved", "reason": "review", "source": "evidence"}
        cfg = {"labels": {"S": {}}, "private_review": {"A": approved, "S": approved, "U": {"status": "approved"}}}
        self.assertEqual((status("A", cfg), status("S", cfg), status("U", cfg)),
                         ("approved", "service", "candidate"))
        self.assertTrue(private_payment(dict(kind="payment", sender="A", recipient="S"), cfg, {"A"}))
        self.assertFalse(private_payment(dict(kind="payment", sender="U", recipient="S"), cfg, {"A"}))
        self.assertFalse(private_payment(dict(kind="path_send", sender="A", recipient="S"), cfg, {"A"}))
        self.assertFalse(private_signal(dict(address="A", kind="large"), cfg))
        self.assertTrue(private_signal(dict(address="A", kind="large", private_direct=True), cfg))
        self.assertFalse(private_signal(dict(address="S", kind="balance_jump"), cfg))
