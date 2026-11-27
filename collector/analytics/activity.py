"""Observed wallet inactivity and repeated direct XLM interactions."""
from collections import defaultdict
from datetime import datetime

from collector.analytics.signals import record
from collector.model import stroops, xlm


def inactivity(wallet, time, threshold):
    """Bound inactivity by the wallet's own observation start and stream progress."""
    start = max(filter(None, (wallet.get("first_seen"), wallet.get("last_activity"))), default=None)
    if not start or not time or time < start:
        return None
    days = (datetime.fromisoformat(time) - datetime.fromisoformat(start)).days
    return dict(days=days, dormant=days >= threshold, since=start, through=time, threshold=threshold)


def observe_activity(wallet, address, time, token, threshold):
    previous = wallet.get("last_activity")
    if previous is not None and time <= previous:
        return None
    status = inactivity(wallet, time, threshold)
    wallet["last_activity"] = time
    if not wallet.get("label") and status and status["dormant"]:
        days = status["days"]
        return record(f"{token}:{address}:resumed", "activity_resumed", "medium",
                      f"Замечена операция после {days} суток без наблюдаемой активности", time, address)


def direct_interactions(operations, wallets, cutoff):
    """Show evidence for repeated transfers, never infer common ownership."""
    addresses = {address for address, wallet in wallets.items() if not wallet.get("label")}
    groups = defaultdict(lambda: {"hashes": set(), "days": set(), "rows": []})
    for row in operations:
        left, right = row["sender"], row["recipient"]
        if (row["kind"] != "payment" or row["time"] < cutoff or
                left not in addresses or right not in addresses or left == right):
            continue
        evidence = groups[tuple(sorted((left, right)))]
        evidence["hashes"].add(row["hash"])
        evidence["days"].add(row["time"][:10])
        evidence["rows"].append(row)
    result = []
    for (left, right), group in groups.items():
        transactions = len(group["hashes"])
        days = len(group["days"])
        if transactions < 3 or days < 2:
            continue
        rows = sorted(group["rows"], key=lambda row: (row["time"], row["id"]), reverse=True)
        examples = list(dict.fromkeys(row["hash"] for row in rows))[:3]
        result.append(dict(left=left, right=right, transactions=transactions, days=days,
                           amount=xlm(sum(stroops(row["amount"]) for row in rows)),
                           last=rows[0]["time"], examples=examples))
    return sorted(result, key=lambda row: (-row["transactions"], -stroops(row["amount"]), row["left"], row["right"]))
