"""Wallet balances and direct XLM flows for Telegram's closed UTC windows."""
from datetime import date, timedelta
from decimal import Decimal

from collector.analytics.payment_history import summarize_history
from collector.storage import load


def wallet_contexts(root, addresses, now):
    state = load(root / "state.json", {})
    day_cache = {}

    def balance_at(address, boundary):
        for day in (boundary, boundary - timedelta(days=1)):
            if day not in day_cache:
                day_cache[day] = list(load(root / "archive" / f"{day}.json", {}).get("snapshots", {}).values())
            cutoff = boundary.isoformat() + "T00:00:00Z"
            samples = [row for row in day_cache[day] if row["address"] == address and row["time"] <= cutoff]
            if samples:
                return max(samples, key=lambda row: row["time"])["balance"]
        return None

    contexts = {}
    for address in addresses:
        wallet = state.get("wallets", {}).get(address)
        if not wallet:
            continue
        history = summarize_history(state.get("payment_history", {}).get(address))
        end = date.fromisoformat(history["end"] if history else now[:10])
        after = balance_at(address, end)
        contexts[address] = dict(balance=wallet["balance"], updated=wallet["updated"], end=end.isoformat(), periods={
            days: dict(before=balance_at(address, end - timedelta(days=days)), after=after,
                       flows=history["periods"][str(days)] if history else None)
            for days in (7, 30)
        })
    return contexts


def amount_text(amount):
    value = Decimal(amount)
    precision = 7 if 0 < abs(value) < Decimal("0.01") else 2
    return f"{value:,.{precision}f}".replace(",", " ").replace(".", ",")


def present(context):
    balance = amount_text(context["balance"])
    updated = context["updated"][:16].replace("T", " ")
    lines = [f"Последний баланс: {balance} XLM · {updated} UTC",
             f"Периоды до {context['end']} UTC · суммы в XLM"]
    for days, row in context["periods"].items():
        before, after = row["before"], row["after"]
        line = f"{days} дн."
        if before is not None and after is not None:
            line += f" · было {amount_text(before)} → стало {amount_text(after)}"
        else:
            line += " · для сравнения баланса не хватает снимков"
        lines.append(line)
        flows = row["flows"]
        if flows and flows["complete"]:
            sign = "+" if Decimal(flows["net"]) > 0 else ""
            lines.append("Платежи: получено " + amount_text(flows["incoming"]) +
                         ", отправлено " + amount_text(flows["outgoing"]) +
                         ", итог " + sign + amount_text(flows["net"]))
        else:
            lines.append("Платежи: история за период неполная")
    return "\n".join(lines)
