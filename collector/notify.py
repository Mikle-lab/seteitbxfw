"""Optional Telegram digest for persisted high-severity alerts."""
import argparse
from datetime import datetime, timedelta, timezone
from http.client import HTTPException, HTTPSConnection
import json
import os
from pathlib import Path
import re

from collector.model import valid_address
from collector.storage import Store, load, write

RADAR = "https://mikle-lab.github.io/seteitbxfw/#anomalies"
LEVELS = {"high": "Высокая", "critical": "Критическая"}
MAX_ALERTS = 8


class DeliveryError(Exception):
    """An error suitable for public workflow logs."""


def send_message(token, chat, message):
    connection = HTTPSConnection("api.telegram.org", timeout=15)
    try:
        body = json.dumps(dict(chat_id=chat, text=message, link_preview_options={"is_disabled": True}),
                          ensure_ascii=False).encode("utf-8")
        connection.request("POST", f"/bot{token}/sendMessage", body, {"Content-Type": "application/json"})
        response = connection.getresponse()
        if response.status != 200:
            raise DeliveryError(f"Telegram returned HTTP {response.status}")
        if json.loads(response.read(65536)).get("ok") is not True:
            raise DeliveryError("Telegram did not confirm the message")
    except (OSError, HTTPException, ValueError, AttributeError):
        raise DeliveryError("Telegram transport failed") from None
    finally:
        connection.close()


def digest(alerts):
    parts = ["XLM Radar · важные сигналы"]
    for row in alerts:
        reason = " ".join(str(row["reason"]).split())[:180]
        line = f'{LEVELS[row["level"]]} · {row["time"][:19].replace("T", " ")} UTC\n{reason}'
        if row.get("amount") is not None:
            line += f' · {row["amount"]} XLM'
        address = row.get("address")
        if valid_address(address):
            line += f"\nhttps://stellar.expert/explorer/public/account/{address}"
        parts.append(line)
    parts.append(RADAR)
    return "\n\n".join(parts)


def notify(store, now, send):
    path = store.root / "notifications.json"
    previous = load(path)
    if previous is None:
        write(path, dict(enabled_since=now, sent={}))
        return 0
    enabled = previous["enabled_since"]
    cutoff = max(enabled, (datetime.fromisoformat(now) - timedelta(days=2)).isoformat().replace("+00:00", "Z"))
    confirmed = {identifier: time for identifier, time in previous["sent"].items() if time >= cutoff}
    pending = {}
    for path_day in (store.root / "archive").glob("*.json"):
        if cutoff[:10] <= path_day.stem <= now[:10]:
            archive = load(path_day, {})
            for row in archive.get("signals", {}).values():
                identifier = row["id"]
                if (enabled < row["time"] <= now and row["time"] >= cutoff and
                        row["level"] in LEVELS and identifier not in confirmed):
                    pending[identifier] = row
    alerts = sorted(pending.values(), key=lambda row: (row["time"], row["id"]))[:MAX_ALERTS]
    if alerts:
        send(digest(alerts))
        confirmed.update((row["id"], row["time"]) for row in alerts)
    if alerts or confirmed != previous["sent"]:
        write(path, dict(enabled_since=enabled, sent=confirmed))
    return len(alerts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("data"))
    args = parser.parse_args()
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token and not chat:
        print("Telegram notification secrets are unset. Delivery is disabled.")
        return 0
    if not re.fullmatch(r"\d+:[A-Za-z0-9_-]+", token) or not re.fullmatch(r"-?\d+|@[A-Za-z0-9_]{5,}", chat):
        print("Configure both Telegram secrets with a bot token and numeric chat ID or channel username.")
        return 1
    store = Store(args.data)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    try:
        with store.locked():
            delivered = notify(store, now, lambda message: send_message(token, chat, message))
    except DeliveryError as error:
        print(str(error))
        return 1
    print(f"Telegram alerts confirmed: {delivered}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
