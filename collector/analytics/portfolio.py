"""Horizon account inventory and indicative XLM order-book valuations."""
from datetime import datetime, timedelta
import re
from decimal import Decimal

from collector.model import valid_address

QUOTE_AGE = timedelta(minutes=45)


def balance_assets(account):
    return [
        dict(kind=row["asset_type"], amount=row["balance"], code=row.get("asset_code"),
             issuer=row.get("asset_issuer"), pool=row.get("liquidity_pool_id"))
        for row in (account or {}).get("balances", []) if Decimal(row["balance"]) != 0
    ]


def asset_key(asset):
    pool = asset.get("pool")
    if pool and re.fullmatch(r"[a-f0-9]{64}", pool):
        return "pool:" + pool
    return (asset["code"] + ":" + asset["issuer"]
            if asset.get("code") and valid_address(asset.get("issuer")) else None)


def market_midpoint(book):
    if not book["bids"] or not book["asks"]:
        return None
    bid, ask = book["bids"][0], book["asks"][0]
    buy, sell = Decimal(bid["price"]), Decimal(ask["price"])
    if not 0 < buy <= sell or (sell - buy) / buy > Decimal("0.20"):
        return None
    if min(Decimal(bid["amount"]), Decimal(ask["amount"])) < 5:
        return None
    return format((buy + sell) / 2, "f")


def is_current(quote, now, maximum=QUOTE_AGE):
    if not quote or not quote.get("time"):
        return False
    age = datetime.fromisoformat(now) - datetime.fromisoformat(quote["time"])
    return timedelta(minutes=-1) <= age <= maximum


def refresh_markets(api, state, config, now):
    budget = config.get("portfolio_quote_pages", 0)
    if not budget:
        return
    quotes = state.setdefault("asset_quotes", {})
    assets = {}
    for wallet in state["wallets"].values():
        if wallet.get("label"):
            continue
        for asset in wallet.get("assets", []):
            key = asset_key(asset)
            if key is not None:
                assets[key] = asset
    for key in list(assets):
        pool_quote = quotes.get(key, {})
        for reserve in pool_quote.get("reserves", []):
            reserve_key = asset_key(reserve)
            if reserve_key:
                assets.setdefault(reserve_key, reserve)
    for key in list(quotes):
        if key not in assets:
            del quotes[key]
    for key in sorted(assets, key=lambda item: (quotes.get(item, {}).get("time", ""), item))[:budget]:
        if api.requests_remaining <= 10:
            break
        if is_current(quotes.get(key), now):
            break
        asset = assets[key]
        try:
            if key.startswith("pool:"):
                pool = api.get("/liquidity_pools/" + asset["pool"])
                reserves = []
                for row in pool["reserves"]:
                    if row["asset"] == "native":
                        reserves.append(dict(kind="native", amount=row["amount"]))
                    else:
                        code, issuer = row["asset"].split(":", 1)
                        kind = "credit_alphanum4" if len(code) <= 4 else "credit_alphanum12"
                        reserves.append(dict(kind=kind, code=code, issuer=issuer, amount=row["amount"]))
                quotes[key] = dict(time=now, shares=pool["total_shares"], reserves=reserves)
                continue
            result = api.get("/order_book", selling_asset_type=asset["kind"], selling_asset_code=asset["code"],
                             selling_asset_issuer=asset["issuer"], buying_asset_type="native", limit=1)
            quotes[key] = dict(time=now, xlm=market_midpoint(result))
        except (OSError, RuntimeError, KeyError, ValueError, ArithmeticError):
            if key not in quotes:
                quotes[key] = dict(time=now, xlm=None)


def value_portfolio(wallet, markets, spot, now):
    if "assets" not in wallet:
        return None
    value = Decimal(0)
    count = 0
    result = []
    current = Decimal(spot["price"]) if is_current(spot, now, timedelta(minutes=15)) else None

    def unit_usd(asset):
        if current is None:
            return None
        if asset["kind"] == "native":
            return current
        quote = markets.get(asset_key(asset))
        if not is_current(quote, now):
            return None
        if asset["kind"] == "liquidity_pool_shares":
            if Decimal(quote.get("shares", "0")) <= 0 or not quote.get("reserves"):
                return None
            values = [(Decimal(row["amount"]), unit_usd(row)) for row in quote["reserves"]]
            if any(price is None for _, price in values):
                return None
            return sum(amount * price for amount, price in values) / Decimal(quote["shares"])
        return Decimal(quote["xlm"]) * current if quote.get("xlm") is not None else None

    for asset in wallet["assets"]:
        market = unit_usd(asset)
        usd = Decimal(asset["amount"]) * market if market is not None else None
        if usd is not None:
            value += usd
            count += 1
        result.append(dict(**asset, usd=format(usd, ".2f") if usd is not None else None))
    result.sort(key=lambda row: (row["usd"] is None, -Decimal(row["usd"] or 0), row.get("code") or ""))
    return dict(assets=result, usd=format(value, ".2f") if count or not result else None,
                valued=count, updated=wallet["updated"], quote_time=spot["time"] if current is not None else None)
