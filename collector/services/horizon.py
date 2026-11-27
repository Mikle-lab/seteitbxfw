"""Horizon HTTP transport and pagination."""
import json
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class Horizon:
    def __init__(self, config):
        self.base = config["horizon"].rstrip("/")
        self.spacing = 1 / config["requests_per_second"]
        self.limit = config["max_requests"]
        self.attempts = 0
        self.next_request = 0

    @property
    def requests_remaining(self):
        return self.limit - self.attempts

    def get(self, path, *, missing=False, **params):
        url = self.base + path
        if params:
            url += "?" + urlencode(params)
        for attempt in range(5):
            if self.attempts >= self.limit:
                raise RuntimeError("Horizon request budget exhausted")
            time.sleep(max(0, self.next_request - time.monotonic()))
            self.next_request = time.monotonic() + self.spacing
            self.attempts += 1
            delay = 2 ** attempt
            try:
                request = Request(url, headers={"Accept": "application/json", "User-Agent": "XLM-Radar/0.1"})
                with urlopen(request, timeout=20) as response:
                    return json.load(response)
            except HTTPError as error:
                if error.code == 404 and missing:
                    return None
                if error.code not in (408, 429, 500, 502, 503, 504) or attempt == 4:
                    raise
                retry = error.headers.get("Retry-After")
                if retry:
                    try:
                        seconds = int(retry)
                    except ValueError:
                        seconds = (parsedate_to_datetime(retry) - datetime.now(timezone.utc)).total_seconds()
                    if seconds > 90:
                        raise
                    delay = max(delay, seconds)
            except (URLError, TimeoutError):
                if attempt == 4:
                    raise
            time.sleep(delay)

    def operations(self, cursor, limit):
        result = self.get("/operations", cursor=cursor, limit=limit, order="asc", include_failed="false")
        return result["_embedded"]["records"]

    def trades(self, cursor, limit):
        result = self.get("/trades", cursor=cursor, limit=limit, order="asc")
        return result["_embedded"]["records"]

    def balance(self, address):
        account = self.get("/accounts/" + address, missing=True)
        if account is None:
            return 0
        from collector.model import stroops
        return next(stroops(row["balance"]) for row in account["balances"] if row["asset_type"] == "native")
