import unittest

from collector.analytics.portfolio import asset_key, balance_assets, market_midpoint, value_portfolio
from test_collector import RECIPIENT

NOW = "2026-11-27T12:00:00Z"
POOL = "a" * 64
XLM = dict(kind="native", amount="250.0000000")
TOKEN = dict(kind="credit_alphanum4", code="USD", issuer=RECIPIENT, amount="100.0000000")
SPOT = dict(price="0.20", time=NOW)


class PortfolioTests(unittest.TestCase):
    def test_exact_value_and_unknown_tokens(self):
        other = dict(TOKEN, code="OTHER")
        wallet = dict(assets=[XLM, TOKEN, other], updated=NOW)
        quotes = {asset_key(TOKEN): dict(xlm="4.5", time=NOW)}
        result = value_portfolio(wallet, quotes, SPOT, NOW)
        self.assertEqual((result["usd"], result["valued"]), ("140.00", 2))
        self.assertIsNone(next(row for row in result["assets"] if row.get("code") == "OTHER")["usd"])
        stale = value_portfolio(wallet, quotes, SPOT, "2026-11-27T12:15:01Z")
        self.assertIsNone(stale["usd"])

    def test_token_quotes_require_identical_issuer(self):
        self.assertIsNone(value_portfolio(dict(assets=[TOKEN], updated=NOW), {}, SPOT, NOW)["usd"])
        inventory = balance_assets({"balances":[dict(asset_type="native", balance="2"),
                                               dict(asset_type="credit_alphanum4", balance="0")]})
        self.assertEqual(len(inventory), 1)

    def test_orderbook_rejects_wide_or_empty_markets(self):
        book = dict(bids=[dict(price="2", amount="10")], asks=[dict(price="2.1", amount="10")])
        self.assertEqual(market_midpoint(book), "2.05")
        self.assertIsNone(market_midpoint(dict(book, asks=[dict(price="3", amount="10")])))
        self.assertIsNone(market_midpoint(dict(book, asks=[])))

    def test_pool_value_requires_every_reserve_quote(self):
        share = dict(kind="liquidity_pool_shares", amount="10", pool=POOL)
        wallet = dict(assets=[share], updated=NOW)
        quote = {asset_key(share): dict(time=NOW, shares="100", reserves=[XLM, TOKEN])}
        self.assertIsNone(value_portfolio(wallet, quote, SPOT, NOW)["usd"])
        quote[asset_key(TOKEN)] = dict(xlm="4.5", time=NOW)
        self.assertEqual(value_portfolio(wallet, quote, SPOT, NOW)["usd"], "14.00")
