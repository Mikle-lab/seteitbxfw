"""Daily XLM/USD closing prices from the public Coinbase Exchange API."""
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from urllib.parse import urlencode
from urllib.request import Request, urlopen

PRICE_API = "https://api.exchange.coinbase.com/products/XLM-USD/candles"
SOURCE = "https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles"


def normalize_candles(rows, start, today):
    prices = {}
    for row in rows:
        if not isinstance(row, list) or len(row) < 5 or not isinstance(row[0], int):
            continue
        day = datetime.fromtimestamp(row[0], timezone.utc).date()
        close = Decimal(str(row[4]))
        if start <= day < today and close.is_finite() and close > 0:
            key = day.isoformat()
            prices[key] = dict(id=key, time=key + "T23:59:59Z", close=format(close, "f"))
    return prices


def collect_prices(state, now):
    instant = datetime.fromisoformat(now)
    today = instant.date()
    yesterday = (today - timedelta(days=1)).isoformat()
    saved = set(state.get("price_days", ()))
    if yesterday in saved:
        return []
    previous = state.get("price_attempt")
    if previous and instant - datetime.fromisoformat(previous) < timedelta(minutes=30):
        return []
    state["price_attempt"] = now
    start = today - timedelta(days=7 if saved else 90)
    query = urlencode(dict(granularity=86400, start=start.isoformat() + "T00:00:00Z",
                           end=today.isoformat() + "T00:00:00Z"))
    request = Request(PRICE_API + "?" + query, headers={"Accept": "application/json", "User-Agent": "XLM-Radar/0.3"})
    with urlopen(request, timeout=12) as response:
        rows = json.load(response, parse_float=Decimal)
    if not isinstance(rows, list):
        raise ValueError("Unexpected candle response")
    prices = normalize_candles(rows, start, today)
    state["price_days"] = sorted(saved | prices.keys())[-100:]
    state["price_through"] = max(state["price_days"], default=None)
    if yesterday in prices:
        state.pop("price_error", None)
    else:
        state["price_error"] = now
    return [row for day, row in sorted(prices.items()) if day not in saved]


def price_history(rows):
    known = {row["time"][:10]: Decimal(row["close"]) for row in rows}
    history = []
    for day, price in sorted(known.items()):
        yesterday = (datetime.fromisoformat(day).date() - timedelta(days=1)).isoformat()
        previous = known.get(yesterday)
        percent = round((price - previous) * 100 / previous, 4) if previous else None
        history.append(dict(day=day, usd=format(price, "f"),
                            percent=format(percent, "f") if percent is not None else None))
    return history
