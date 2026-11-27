"""Exchange flows and confirmed Horizon trade fills."""
import re

from collector.model import stroops, valid_address, xlm


def exchange_flow(operation, labels):
    if operation["type"] != "payment" or operation.get("asset_type") != "native":
        return None
    sender, recipient = operation.get("from"), operation.get("to")
    outgoing = labels.get(sender, {}).get("type") == "exchange"
    incoming = labels.get(recipient, {}).get("type") == "exchange"
    if outgoing == incoming:
        return None
    address = recipient if incoming else sender
    amount = stroops(operation["amount"])
    if amount <= 0:
        return None
    return dict(id=operation["paging_token"], time=operation["created_at"], amount=xlm(amount),
                direction="in" if incoming else "out", address=address,
                sender=sender, recipient=recipient, hash=operation["transaction_hash"])


def trade_key(token):
    return tuple(map(int, token.split("-")))


def xlm_fill(trade, sources):
    base = trade.get("base_asset_type") == "native"
    counter = trade.get("counter_asset_type") == "native"
    if base == counter:
        return None
    native, other = ("base", "counter") if base else ("counter", "base")
    amount = stroops(trade[native + "_amount"])
    if amount <= 0:
        return None
    token = trade["paging_token"]
    operation = token.split("-", 1)[0]
    seller = trade.get(native + "_account")
    buyer = trade.get(other + "_account")
    initiator = sources.get(operation)
    direction = None
    if initiator and seller != buyer:
        if initiator == seller:
            direction = "sell"
        elif initiator == buyer:
            direction = "buy"
    issuer = trade.get(other + "_asset_issuer", "")
    if not valid_address(issuer):
        return None
    code = trade.get(other + "_asset_code", "")
    if not re.fullmatch(r"[a-zA-Z0-9]{1,12}", code):
        return None
    return dict(id=token, time=trade["ledger_close_time"], amount=xlm(amount), code=code,
                issuer=issuer, venue=trade["trade_type"], buyer=buyer, seller=seller,
                direction=direction, operation=operation)


def summarize_fills(fills):
    """Persist minute-level totals and the largest executions per scan."""
    grouped = {}
    for fill in fills:
        minute = fill["time"][:16] + ":00Z"
        key = (minute, fill["code"], fill["issuer"], fill["direction"])
        summary = grouped.setdefault(key, dict(id=fill["id"], time=minute, code=fill["code"],
                                               issuer=fill["issuer"], direction=fill["direction"],
                                               units=0, count=0))
        summary["units"] += stroops(fill["amount"])
        summary["count"] += 1
    summaries = []
    for item in grouped.values():
        item["amount"] = xlm(item.pop("units"))
        summaries.append(item)
    top = sorted(fills, key=lambda row: (-stroops(row["amount"]), row["id"]))[:20]
    return top, summaries


def collect_trades(api, state, start, head, time, cfg):
    previous = state["cursors"].get("trades")
    cursor = previous or str((max(head - 30, 1) << 32)) + "-0"
    events = []
    caught_up = False
    for _ in range(cfg["trade_pages"]):
        if api.requests_remaining <= 12:
            break
        rows = api.trades(cursor, cfg["page_limit"])
        for row in rows:
            token = row["paging_token"]
            operation, _ = trade_key(token)
            if operation >> 32 > head:
                caught_up = True
                break
            if trade_key(token) <= trade_key(cursor):
                continue
            cursor = token
            fill = xlm_fill(row, state["trade_sources"])
            if fill:
                events.append(fill)
        if caught_up or len(rows) < cfg["page_limit"]:
            caught_up = True
            break
    if previous is None and not caught_up and cursor.endswith("-0"):
        return []
    state["cursors"]["trades"] = cursor
    state.setdefault("dex_coverage_from", start)
    state["dex_updated"] = time
    state["dex_caught_up"] = caught_up
    state.pop("dex_error", None)
    return events
