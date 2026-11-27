"""Optional Telegram digest for persisted high-severity alerts."""
import argparse
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from http.client import HTTPException, HTTPSConnection
import json
import os
from pathlib import Path
import re

from collector.analytics.alert_context import amount_text, present, wallet_contexts
from collector.analytics.review import private_signal
from collector.model import valid_address
from collector.storage import Store, load, write

LEVELS = {"high": "Высокая", "critical": "Критическая"}
MAX_ALERTS = 8
TELEGRAM_LIMIT = 4096


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
        result = json.loads(response.read(65536))
        if result.get("ok") is not True:
            raise DeliveryError("Telegram did not confirm the message")
        message_id = result.get("result", {}).get("message_id")
        if type(message_id) is not int or message_id < 1:
            raise DeliveryError("Telegram did not return a message ID")
        return message_id
    except (OSError, HTTPException, ValueError, AttributeError):
        raise DeliveryError("Telegram transport failed") from None
    finally:
        connection.close()


def closing_rate(archive, day):
    for days_ago in range(1, 8):
        previous = day - timedelta(days=days_ago)
        data = load(archive / f"{previous}.json", {})
        candle = data.get("prices", {}).get(previous.isoformat())
        if candle:
            return previous, Decimal(candle["close"])
    return None


def digest(alerts, rates, contexts):
    parts = ["XLM Radar · важные сигналы"]
    for row in alerts:
        reason = " ".join(str(row["reason"]).split())[:180]
        line = f'{LEVELS[row["level"]]} · {row["time"][:19].replace("T", " ")} UTC\n{reason}'
        if row.get("amount") is not None:
            line += f' · {row["amount"]} XLM'
            rate = rates.get(row["time"][:10])
            if rate is not None:
                day, price = rate
                amount = Decimal(row["amount"]) * price
                dollars = f"{abs(amount):,.2f}".replace(",", " ").replace(".", ",")
                sign = "−" if amount < 0 else ""
                line += f" (≈ {sign}${dollars}, курс закрытия {day:%d.%m} UTC)"
        if row.get("balance_before") is not None and row.get("balance_after") is not None:
            line += ("\nБаланс по сигналу: " + amount_text(row["balance_before"]) +
                     " → " + amount_text(row["balance_after"]) + " XLM")
        address = row.get("address")
        context = contexts.get(address)
        if context:
            line += "\n" + present(context)
        if valid_address(address):
            line += f"\nhttps://stellar.expert/explorer/public/account/{address}"
        parts.append(line)
    return "\n\n".join(parts)


def notify(store, now, send, config=None):
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
                        row["level"] in LEVELS and identifier not in confirmed and
                        (config is None or private_signal(row, config))):
                    pending[identifier] = row
    alerts = sorted(pending.values(), key=lambda row: (row["time"], row["id"]))[:MAX_ALERTS]
    if alerts:
        dates = {row["time"][:10] for row in alerts if row.get("amount") is not None}
        rates = {day: closing_rate(store.root / "archive", date.fromisoformat(day)) for day in dates}
        contexts = wallet_contexts(store.root, {row.get("address") for row in alerts}, now)
        message = digest(alerts, rates, contexts)
        while len(alerts) > 1 and len(message.encode("utf-16-le")) // 2 > TELEGRAM_LIMIT:
            alerts.pop()
            message = digest(alerts, rates, contexts)
        send(message)
        confirmed.update((row["id"], row["time"]) for row in alerts)
    if alerts or confirmed != previous["sent"]:
        write(path, dict(enabled_since=enabled, sent=confirmed))
    return len(alerts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--test-channel", help="Send one test message to the matching configured public channel")
    args = parser.parse_args()
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token and not chat:
        print("Telegram notification secrets are unset. Delivery is disabled.")
        return 1 if args.test_channel else 0
    if not re.fullmatch(r"\d+:[A-Za-z0-9_-]+", token) or not re.fullmatch(r"-?\d+|@[A-Za-z0-9_]{5,}", chat):
        print("Configure both Telegram secrets with a bot token and numeric chat ID or channel username.")
        return 1
    if args.test_channel:
        if not chat.startswith("@") or args.test_channel.casefold() != chat.casefold():
            print("Configured Telegram channel does not match the requested public channel.")
            return 1
        try:
            message_id = send_message(token, chat,
                                      "Тест XLM Radar. Это проверка доставки уведомлений.")
        except DeliveryError as error:
            print(str(error))
            return 1
        print(f"Telegram confirmed test message {message_id}.")
        return 0
    store = Store(args.data)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    try:
        with store.locked():
            delivered = notify(store, now, lambda message: send_message(token, chat, message),
                               load(Path("config.json")))
    except DeliveryError as error:
        print(str(error))
        return 1
    print(f"Telegram alerts confirmed: {delivered}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
