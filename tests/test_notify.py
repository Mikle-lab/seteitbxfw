from datetime import datetime
import json
import tempfile
import unittest
from unittest.mock import Mock, patch

from collector.freshness import fresh
from collector.notify import DeliveryError, notify, send_message
from collector.storage import Store, load, write


ACTIVATED = "2026-11-27T14:00:00Z"
LATER = "2026-11-27T14:30:00Z"


def alert(id_, time, level="high"):
    return dict(id=id_, time=time, level=level, reason="Example signal", amount="50000")


class NotifyTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.store = Store(folder.name)
        self.archive = self.store.root / "archive" / "2026-11-27.json"
        self.sent = Mock()

    def test_activation_skips_history_and_retry_skips_delivered(self):
        old, new = alert("old", "2026-11-27T13:59:59Z"), alert("new", "2026-11-27T14:01:00Z")
        low = alert("low", "2026-11-27T14:02:00Z", "low")
        write(self.archive, {"signals": {row["id"]: row for row in (old, new, low)}})
        self.assertEqual(notify(self.store, ACTIVATED, self.sent), 0)
        self.sent.assert_not_called()
        self.assertEqual(notify(self.store, LATER, self.sent), 1)
        self.assertIn("50000 XLM", self.sent.call_args.args[0])
        self.assertNotIn("github.io", self.sent.call_args.args[0])
        self.assertEqual(notify(self.store, LATER, self.sent), 0)
        self.sent.assert_called_once()

    def test_usd_uses_previous_close_and_keeps_wallet_link(self):
        from test_collector import RECIPIENT

        notify(self.store, ACTIVATED, self.sent)
        write(self.archive.with_name("2026-11-26.json"), {"prices": {"2026-11-26": {"close": "0.125"}}})
        write(self.archive, {"prices": {"2026-11-27": {"close": "0.500"}}, "signals": {
            "drop": dict(alert("drop", "2026-11-27T14:03:00Z"), address=RECIPIENT, amount="-50000", balance_before="1200000", balance_after="1150000")
        }})
        notify(self.store, LATER, self.sent)
        message = self.sent.call_args.args[0]
        self.assertIn("-50000 XLM (≈ −$6 250,00, курс закрытия 26.11 UTC)", message)
        self.assertIn("Баланс по сигналу: 1 200 000,00 → 1 150 000,00 XLM", message)
        self.assertTrue(message.endswith("https://stellar.expert/explorer/public/account/" + RECIPIENT))

    def test_failure_preserves_checkpoint(self):
        notify(self.store, ACTIVATED, self.sent)
        write(self.archive, {"signals": {"new": alert("new", "2026-11-27T14:01:00Z")}})
        self.sent.side_effect = DeliveryError("failed")
        with self.assertRaises(DeliveryError):
            notify(self.store, LATER, self.sent)
        self.assertEqual(load(self.store.root / "notifications.json")["sent"], {})
        self.sent.side_effect = None
        self.assertEqual(notify(self.store, LATER, self.sent), 1)

    def test_telegram_transport_posts_plain_text_and_checks_ack(self):
        with patch("collector.notify.HTTPSConnection") as connection:
            transport = connection.return_value
            transport.getresponse.return_value = Mock(status=200)
            transport.getresponse.return_value.read.return_value = b'{"ok":true,"result":{"message_id":42}}'
            self.assertEqual(send_message("123:fixture", "-456", "Тест"), 42)
            method, path, body, _ = transport.request.call_args.args
            self.assertEqual((method, path), ("POST", "/bot123:fixture/sendMessage"))
            self.assertEqual(json.loads(body)["text"], "Тест")
            transport.getresponse.return_value.status = 429
            with self.assertRaisesRegex(DeliveryError, "^Telegram returned HTTP 429$"):
                send_message("123:fixture", "-456", "Test")

    def test_backup_only_skips_recent_success(self):
        now = datetime.fromisoformat(LATER)
        self.assertFalse(fresh({}, now))
        self.assertFalse(fresh({"last_success": ACTIVATED}, now))
        self.assertTrue(fresh({"last_success": "2026-11-27T14:20:00Z"}, now))
        self.assertFalse(fresh({"last_success": "2026-11-27T14:15:00Z"}, now))
        self.assertFalse(fresh({"last_success": "2026-11-27T14:31:00Z"}, now))
