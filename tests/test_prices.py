from datetime import date, datetime, timezone
from io import BytesIO
import json
import unittest
from urllib.error import URLError
from unittest.mock import patch

from collector.services.prices import collect_prices, normalize_candles, price_history


def candle(day, close):
    instant = datetime.fromisoformat(day).replace(tzinfo=timezone.utc)
    return [int(instant.timestamp()), 0, 0, 0, close, 100]


class PriceTests(unittest.TestCase):
    def test_only_closed_positive_candles_in_range(self):
        rows = [candle("2026-11-24", 0.1), candle("2026-11-25", 0),
                candle("2026-11-26", 0.125172), candle("2026-11-27", 0.13)]
        prices = normalize_candles(rows, date(2026, 11, 25), date(2026, 11, 27))
        self.assertEqual(list(prices), ["2026-11-26"])
        self.assertEqual(prices["2026-11-26"]["close"], "0.125172")

    def test_daily_percent_uses_previous_calendar_day(self):
        rows = [candle("2026-11-23", 0.1), candle("2026-11-25", 0.12), candle("2026-11-26", 0.126)]
        values = normalize_candles(rows, date(2026, 11, 21), date(2026, 11, 27))
        result = price_history(values.values())
        self.assertIsNone(result[1]["percent"])
        self.assertEqual(result[2]["percent"], "5.0000")

    def test_retry_interval_and_no_duplicate_close(self):
        state = {}
        with patch("collector.services.prices.urlopen", side_effect=URLError("fixture")):
            with self.assertRaises(URLError):
                collect_prices(state, "2026-11-27T00:20:00Z")
        with patch("collector.services.prices.urlopen") as request:
            self.assertEqual(collect_prices(state, "2026-11-27T00:24:00Z"), [])
            request.assert_not_called()
        payload = json.dumps([candle("2026-11-26", 0.125172)]).encode()
        with patch("collector.services.prices.urlopen", return_value=BytesIO(payload)):
            rows = collect_prices(state, "2026-11-27T00:50:00Z")
            self.assertEqual(len(rows), 1)
        with patch("collector.services.prices.urlopen") as request:
            self.assertEqual(collect_prices(state, "2026-11-27T01:30:00Z"), [])
            request.assert_not_called()
