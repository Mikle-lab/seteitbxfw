"""Deterministic anomaly rules; stable IDs are derived from the source record."""
from decimal import Decimal
from collector.model import category, stroops, xlm


def record(identifier, kind, level, reason, time, address, amount=None, percent=None):
    return dict(id=identifier, kind=kind, level=level, reason=reason, time=time,
                address=address, amount=None if amount is None else xlm(amount), percent=percent)


def balance_signals(address, previous, balance, now, batch, cfg):
    prefix = f"{batch}:{address}"
    threshold = stroops(cfg["whale_min_xlm"])
    if previous is None:
        if balance >= threshold:
            yield record(prefix + ":new", "new", "medium", "Впервые обнаружен баланс от порога китов", now, address, balance)
        return
    delta = balance - previous
    percent = float(round(Decimal(delta) * 100 / previous, 2)) if previous else None
    if previous and abs(delta) >= stroops(cfg["large_xlm"]) and abs(delta) * 100 >= previous * cfg["anomaly_percent"]:
        reason = "Резкий рост баланса" if delta > 0 else "Резкое сокращение баланса"
        level = "critical" if abs(delta) >= threshold and abs(delta) * 100 >= previous * 20 else "high"
        yield record(prefix + ":jump", "balance_jump", level, reason, now, address, delta, percent)
    if previous >= threshold > balance:
        yield record(prefix + ":exit", "exit", "medium", "Баланс опустился ниже порога китов", now, address, delta, percent)
    elif balance >= threshold and balance > previous and category(balance, cfg) != category(previous, cfg):
        yield record(prefix + ":category", "category", "medium", "Переход в более высокую категорию", now, address, delta, percent)
