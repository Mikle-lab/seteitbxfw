import unittest
from collections import defaultdict

from collector.analytics.markets import collect_trades, exchange_flow, xlm_fill
from collector.market_export import build_markets
from test_collector import NOW, PAYMENT, RECIPIENT, SENDER, TOKEN, key

ISSUER = key(3)
LABELS = {RECIPIENT: dict(type="exchange", name="Fixture", confidence="medium", source="https://example.org/")}
FILL = dict(paging_token=TOKEN + "-2", ledger_close_time=NOW, trade_type="liquidity_pool",
            base_asset_type="native", base_amount="1000.0000001",
            counter_asset_type="credit_alphanum4", counter_asset_code="USDC", counter_asset_issuer=ISSUER,
            counter_account=RECIPIENT)


class MarketsTests(unittest.TestCase):
    def test_exchange_flow_tracks_direct_payments_at_any_size(self):
        payment = dict(PAYMENT, amount="10.0000001")
        flow = exchange_flow(payment, LABELS)
        self.assertEqual((flow["direction"], flow["amount"]), ("in", "10.0000001"))
        self.assertEqual(exchange_flow(payment, {SENDER: LABELS[RECIPIENT]})["direction"], "out")
        self.assertIsNone(exchange_flow(payment, {SENDER: LABELS[RECIPIENT], **LABELS}))
        self.assertIsNone(exchange_flow(dict(payment, type="path_payment_strict_send"), LABELS))
        self.assertIsNone(exchange_flow(dict(payment, asset_type="credit_alphanum4"), LABELS))

    def test_fill_direction_uses_initiator_even_for_pool_counterparty(self):
        fill = xlm_fill(FILL, {TOKEN: RECIPIENT})
        self.assertEqual((fill["direction"], fill["amount"], fill["buyer"]), ("buy", "1000.0000001", RECIPIENT))
        self.assertIsNone(xlm_fill(FILL, {})["direction"])
        book = dict(FILL, trade_type="orderbook", base_account=SENDER)
        self.assertEqual(xlm_fill(book, {TOKEN: SENDER})["direction"], "sell")
        self.assertIsNone(xlm_fill(dict(FILL, base_asset_type="credit_alphanum4"), {}))

    def test_trade_cursor_deduplicates_fills_and_stays_independent(self):
        class Api:
            requests_remaining = 100
            fail = False

            def trades(self, cursor, limit):
                if self.fail:
                    raise OSError("fixture downtime")
                return [FILL, FILL, dict(FILL, paging_token=TOKEN + "-10")]

        cfg = {"trade_pages": 2, "page_limit": 6}
        state = {"cursors": {"operations": TOKEN}, "trade_sources": {TOKEN: RECIPIENT}}
        api = Api()
        fills = collect_trades(api, state, NOW, 205, NOW, cfg)
        self.assertEqual(len(fills), 2)
        self.assertEqual(state["cursors"]["trades"], TOKEN + "-10")
        self.assertEqual(state["cursors"]["operations"], TOKEN)
        api.fail = True
        with self.assertRaises(OSError):
            collect_trades(api, state, NOW, 205, NOW, cfg)
        self.assertEqual(state["cursors"]["trades"], TOKEN + "-10")
        api.fail = False
        self.assertEqual(collect_trades(api, state, NOW, 205, NOW, cfg), [])

    def test_markets_keep_unclassified_volume_and_coverage(self):
        flow = exchange_flow(PAYMENT, LABELS)
        fill = xlm_fill(FILL, {})
        state = {"exchange_coverage_from": NOW, "dex_coverage_from": NOW, "caught_up": True, "dex_caught_up": True}
        markets = build_markets(state, LABELS, {}, defaultdict(list), [flow], [fill],
                                {"all": NOW, "24h": "2026-11-26T12:00:00Z"}, lambda rows, _: rows)
        self.assertEqual(markets["dex"]["periods"]["all"]["volume"], "1000.0000001")
        self.assertEqual(markets["dex"]["periods"]["all"]["unknown"], "1000.0000001")
        self.assertEqual(markets["exchanges"]["periods"]["all"]["inflow"], "200000.0000001")
        self.assertFalse(markets["exchanges"]["periods"]["24h"]["complete"])
