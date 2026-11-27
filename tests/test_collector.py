import base64
import binascii
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from collector.analytics.signals import balance_signals
from collector.export import build
from collector.model import movements, stroops, valid_address, xlm
from collector.scan import scan
from collector.services.horizon import Horizon
from collector.storage import Store, load, write
from urllib.error import HTTPError

CFG = json.loads(Path("config.json").read_text())
CFG.update(trade_pages=0, labels={}, collect_usd_prices=False)
NOW = "2026-11-27T12:00:00Z"
LATER = "2026-11-27T12:06:00Z"


def key(number):
    payload = bytes([48, number]) + bytes(31)
    return base64.b32encode(payload + binascii.crc_hqx(payload, 0).to_bytes(2, "little")).decode()


SENDER, RECIPIENT = key(1), key(2)
TOKEN = str((200 << 32) + 1)
PAYMENT = dict(paging_token=TOKEN, type="payment", source_account=SENDER, created_at=NOW,
               asset_type="native", amount="200000.0000001", transaction_hash="a" * 64,
               **{"from": SENDER, "to": RECIPIENT})


class Fixture:
    requests_remaining = 350

    def __init__(self):
        self.amount = stroops("1500000")
        self.fail = False

    def get(self, path):
        if path == "/":
            return dict(history_latest_ledger=205, history_elder_ledger=1)
        return {"closed_at": "2026-11-27T11:50:00Z"}

    def operations(self, cursor, limit):
        return [PAYMENT] if int(cursor) < int(TOKEN) else []

    def balance(self, address):
        if self.fail:
            raise OSError("simulated Horizon outage")
        return self.amount if address == RECIPIENT else 0


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.store = Store(self.root / "data")
        self.api = Fixture()

    def run_scan(self, when):
        with self.store.locked():
            return scan(self.api, self.store, CFG, when)

    def test_exact_stroops_and_valid_keys(self):
        self.assertEqual(xlm(stroops("12345678900.1234567")), "12345678900.1234567")
        self.assertTrue(valid_address(SENDER))
        self.assertFalse(valid_address(SENDER[:-1] + ("A" if SENDER[-1] != "A" else "B")))
        with self.assertRaises(ValueError):
            stroops("0.00000001")

    def test_routed_payment_preserves_endpoint_amounts(self):
        op = dict(PAYMENT, type="path_payment_strict_send", source_asset_type="native",
                  source_amount="220000", amount="210000")
        self.assertEqual(list(movements(op)), [
            ("path_send", SENDER, None, "220000"), ("path_receive", None, RECIPIENT, "210000")])

    def test_failure_preserves_cursor_and_retry_does_not_duplicate(self):
        first = self.run_scan(NOW)
        self.assertEqual(first["processed"], 1)
        self.assertEqual(first["cursors"]["operations"], TOKEN)
        self.api.fail = True
        with self.assertRaises(OSError):
            self.run_scan(LATER)
        self.assertEqual(load(self.store.state), first)
        self.api.fail = False
        self.api.amount = stroops("1700000")
        again = self.run_scan(LATER)
        self.assertEqual(again["processed"], 1)
        self.assertEqual(again["wallets"][RECIPIENT]["balance"], "1700000.0000000")
        archive = load(self.store.root / "archive/2026-11-27.json")
        self.assertEqual(len(archive["operations"]), 1)
        self.assertEqual(len(archive["snapshots"]), 2)
        self.assertEqual(sum(row["kind"] == "balance_jump" for row in archive["signals"].values()), 1)

    def test_replay_after_archive_write_is_idempotent(self):
        state = self.run_scan(NOW)
        archive_path = self.store.root / "archive/2026-11-27.json"
        data = load(archive_path)
        write(self.store.journal, {"state": state, "days": {"2026-11-27": data}})
        with self.store.locked():
            self.assertFalse(self.store.journal.exists())
        self.assertEqual(load(archive_path), data)

    def test_nonblocking_lock_rejects_overlap(self):
        with self.store.locked():
            with self.assertRaises(BlockingIOError):
                with self.store.locked():
                    self.fail("overlapping collector acquired the lock")

    def test_export_preserves_periods_and_pages(self):
        self.run_scan(NOW)
        self.api.amount = stroops("1700000")
        self.run_scan(LATER)
        target = self.root / "site"
        build(self.store.root, target)
        summary = load(target / "data/summary.json")
        self.assertFalse(summary["periods"]["24h"]["complete"])
        self.assertEqual(summary["periods"]["all"]["up"], "200000.0000000")
        self.assertEqual(summary["active"], 1)
        path = summary["sections"]["operations"][0]["path"]
        self.assertEqual(len(load(target / "data" / path)), 1)
        wallet = load(target / "data/wallets" / (RECIPIENT + ".json"))
        self.assertEqual(wallet["wallet"]["periods"]["all"]["received"], "200000.0000001")
        self.assertFalse((target / "data/state.json").exists())

    def test_anomaly_requires_both_thresholds(self):
        signals = list(balance_signals(SENDER, stroops("10000000"), stroops("10100000"), NOW, "id", CFG))
        self.assertFalse(any(row["kind"] == "balance_jump" for row in signals))

    def test_low_request_budget_defers_candidates_without_skipping_the_cursor(self):
        self.api.requests_remaining = 16
        cfg = dict(CFG, candidate_checks=0)
        with self.store.locked():
            first = scan(self.api, self.store, cfg, NOW)
        self.assertEqual(first["cursors"]["operations"], TOKEN)
        self.assertIn(RECIPIENT, first["queue"])
        self.assertNotIn(RECIPIENT, first["wallets"])
        again = self.run_scan(LATER)
        self.assertIn(RECIPIENT, again["wallets"])
        self.assertNotIn(RECIPIENT, again["queue"])

    def test_rate_limit_respects_retry_after(self):
        client = Horizon(CFG)
        error = HTTPError("https://horizon.stellar.org", 429, "rate limit", {"Retry-After": "7"}, None)
        with patch("collector.services.horizon.urlopen", side_effect=[error, error, error, error, error]), \
             patch("collector.services.horizon.time.sleep") as sleep:
            with self.assertRaises(HTTPError):
                client.get("/")
        self.assertEqual(client.attempts, 5)
        self.assertIn(7, [call.args[0] for call in sleep.call_args_list])
