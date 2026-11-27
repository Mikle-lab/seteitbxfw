"""Bounded and resumable account payment histories in UTC days."""
from datetime import date, timedelta
from urllib.error import HTTPError

from collector.analytics.review import status
from collector.model import stroops, xlm

WINDOWS = (1, 7, 30)


def direct_xlm(operation, address):
    if (operation["type"] != "payment" or operation.get("asset_type") != "native"
            or operation.get("transaction_successful") is False):
        return 0
    sender, recipient = operation.get("from"), operation.get("to")
    if sender == recipient:
        return 0
    if address == recipient:
        return stroops(operation["amount"])
    if address == sender:
        return -stroops(operation["amount"])
    return 0


def payment_page(api, address, task, history_floor):
    rows = api.payments(address, task.get("cursor"))
    for row in rows:
        token = row["paging_token"]
        if task.get("cursor") is not None and int(token) >= int(task["cursor"]):
            continue
        task["cursor"] = token
        day = row["created_at"][:10]
        if day < task["start"]:
            task["through"] = task["start"]
            task["complete"] = True
            return
        if day >= task["end"]:
            continue
        task["through"] = (date.fromisoformat(day) + timedelta(days=1)).isoformat()
        change = direct_xlm(row, address)
        if change:
            bucket = task["days"].setdefault(day, [0, 0, 0])
            bucket[0] += max(0, change)
            bucket[1] += max(0, -change)
            bucket[2] += 1
    if len(rows) < api.payment_page_size:
        task["through"] = max(task["start"], history_floor)
        task["complete"] = task["start"] >= history_floor
        task["exhausted"] = True


def update_payment_histories(api, state, config, now, elder):
    limits = config.get("history_pages", 0)
    if not limits or api.requests_remaining < 15:
        return
    day = date.fromisoformat(now[:10])
    history = state.setdefault("payment_history", {})
    eligible = {address for address, wallet in state["wallets"].items()
                if wallet["active"] and status(address, config) != "service"}
    addresses = [address for address in eligible
                 if not (history.get(address, {}).get("exhausted") or history.get(address, {}).get("complete"))
                 or history[address]["end"] < day.isoformat()]
    if not addresses:
        return
    try:
        floor = api.get(f"/ledgers/{elder}")["closed_at"][:10]
        # A day cut by Horizon's retention boundary is incomplete.
        floor = (date.fromisoformat(floor) + timedelta(days=1)).isoformat()
    except (OSError, RuntimeError, ValueError, KeyError):
        return

    ordered = sorted(addresses, key=lambda address: (history.get(address, {}).get("attempt", ""), address))
    for address in ordered[:limits]:
        if api.requests_remaining < 12:
            break
        task = history.get(address)
        if task is None or task.get("complete") or task.get("exhausted"):
            previous = task.get("published") if task else None
            task = dict(end=day.isoformat(), start=(day - timedelta(days=30)).isoformat(), days={},
                        published=previous, attempt=now)
        task["attempt"] = now
        history[address] = task
        try:
            payment_page(api, address, task, floor)
        except HTTPError as error:
            if error.code == 404:
                task["exhausted"] = True
            continue
        except (OSError, RuntimeError, ValueError):
            continue
        if task.get("complete") or task.get("exhausted"):
            task["published"] = {key: task.get(key) for key in ("end", "days", "through", "complete")}


def summarize_history(task):
    if not task:
        return None
    if not task.get("complete") and task.get("published"):
        task = task["published"]
    if not task.get("through"):
        return None
    end = date.fromisoformat(task["end"])
    periods = {}
    for width in WINDOWS:
        start = (end - timedelta(days=width)).isoformat()
        rows = [bucket for day, bucket in task["days"].items() if start <= day < task["end"]]
        incoming = sum(bucket[0] for bucket in rows)
        outgoing = sum(bucket[1] for bucket in rows)
        complete = task["through"] <= start
        periods[str(width)] = dict(incoming=xlm(incoming), outgoing=xlm(outgoing), net=xlm(incoming - outgoing),
                                   payments=sum(bucket[2] for bucket in rows), complete=complete)
    return dict(end=task["end"], through=task["through"], periods=periods)
