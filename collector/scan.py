"""Collect bounded, contiguous batches of successful Stellar operations."""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from collector.analytics.signals import balance_signals, record
from collector.model import category, movements, stroops, valid_address, xlm
from collector.services.horizon import Horizon
from collector.storage import Store, load, write

BALANCE_OPERATIONS = {
    "account_merge", "claim_claimable_balance", "clawback_claimable_balance",
    "liquidity_pool_deposit", "liquidity_pool_withdraw", "manage_buy_offer",
    "manage_sell_offer", "create_passive_sell_offer",
}


def utc():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def scan(api, store, cfg, now):
    state = load(store.state, {"schema": 1, "cursors": {}, "wallets": {}, "processed": 0, "queue": {}})
    if state["schema"] != 1:
        raise ValueError("Unsupported collector schema")
    root = api.get("/")
    head = root["history_latest_ledger"]
    cursor = state["cursors"].get("operations")
    if cursor is None:
        first = max(root["history_elder_ledger"], head - cfg["initial_ledgers"])
        boundary = api.get(f"/ledgers/{first}")
        state["coverage_from"] = boundary["closed_at"]
        cursor = str((first + 1) << 32)
    if int(cursor) >> 32 < root["history_elder_ledger"]:
        raise RuntimeError("Saved cursor is older than Horizon retention; refusing to skip an unscanned interval")

    wallets = state["wallets"]
    queue = state["queue"]
    events = {"operations": [], "signals": [], "snapshots": [], "totals": []}
    large = stroops(cfg["large_xlm"])
    cutoff = stroops(cfg["candidate_min_xlm"])
    whale = stroops(cfg["whale_min_xlm"])
    count = 0
    caught_up = False

    for _ in range(cfg["max_pages"]):
        rows = api.operations(cursor, cfg["page_limit"])
        for operation in rows:
            if int(operation["paging_token"]) >> 32 > head:
                caught_up = True
                break
            token = operation["paging_token"]
            if int(token) <= int(cursor):
                continue
            cursor = token
            count += 1
            time = operation["created_at"]
            state["last_operation"] = time
            kind = operation["type"]
            involved = {operation.get("source_account"), operation.get("into")}
            for index, (movement, sender, recipient, units) in enumerate(movements(operation)):
                amount = stroops(units)
                if amount <= 0 or sender == recipient:
                    continue
                participants = {address for address in (sender, recipient) if valid_address(address)}
                involved.update(participants)
                for address in participants:
                    if amount >= cutoff and address not in wallets:
                        priority = max(amount, int(queue.get(address, [0])[0]))
                        queue[address] = [str(priority), time]
                if amount < large:
                    continue
                identifier = f"{token}:{index}"
                events["operations"].append(dict(id=identifier, time=time, kind=movement,
                                                amount=xlm(amount), sender=sender, recipient=recipient,
                                                hash=operation["transaction_hash"]))
                for address in sorted(participants):
                    events["signals"].append(record(f"{identifier}:{address}", "large", "high" if amount >= whale else "low",
                                                    "Крупное движение XLM", time, address, amount))
            for address in sorted(filter(valid_address, involved)):
                if address in wallets:
                    wallets[address]["last_activity"] = time
                elif kind in BALANCE_OPERATIONS:
                    queue.setdefault(address, ["0", time])
        if caught_up or len(rows) < cfg["page_limit"]:
            caught_up = True
            break

    # Reserve capacity for both previously tracked accounts and new candidates.
    tracked = sorted(wallets, key=lambda address: (wallets[address]["updated"], address))[:cfg["tracked_refresh"]]
    selected = sorted(queue, key=lambda address: (-int(queue[address][0]), queue[address][1], address))[:cfg["candidate_checks"]]
    batch = hashlib.sha256((cursor + ":" + now).encode()).hexdigest()[:20]
    for address in dict.fromkeys(tracked + selected):
        balance = api.balance(address)
        candidate = queue.pop(address, None)
        previous = wallets.get(address)
        label = cfg["labels"].get(address)
        if previous is None and balance < whale and label is None:
            continue
        prior_balance = stroops(previous["balance"]) if previous else None
        if label is None:
            events["signals"].extend(balance_signals(address, prior_balance, balance, now, batch, cfg))
        balance_text = xlm(balance)
        wallet = dict(previous or dict(first_seen=now, minimum=balance_text, maximum=balance_text))
        wallet.update(balance=balance_text, category=category(balance, cfg), updated=now,
                      label=label, active=balance >= whale,
                      minimum=xlm(min(balance, stroops(wallet["minimum"]))),
                      maximum=xlm(max(balance, stroops(wallet["maximum"]))))
        if candidate:
            wallet["last_activity"] = candidate[1]
        wallets[address] = wallet
        if prior_balance != balance or wallet.get("snapshot_day") != now[:10]:
            events["snapshots"].append(dict(id=f"{batch}:{address}", time=now, address=address, balance=balance_text,
                                            delta=None if prior_balance is None else xlm(balance - prior_balance),
                                            previous_time=previous["updated"] if previous else None))
            wallet["snapshot_day"] = now[:10]

    # Retain a bounded candidate queue; tracked addresses and archives are never pruned.
    state["queue"] = dict(sorted(queue.items(), key=lambda item: (-int(item[1][0]), item[1][1], item[0]))[:8000])
    active = [wallet for wallet in wallets.values() if wallet["active"] and not wallet["label"]]
    private_changes = [stroops(row["delta"]) for row in events["snapshots"]
                       if row["delta"] is not None and not wallets[row["address"]]["label"]]
    events["totals"].append(dict(id=batch, time=now,
                                 up=xlm(sum(max(0, change) for change in private_changes)),
                                 down=xlm(sum(max(0, -change) for change in private_changes)),
                                 balance=xlm(sum(stroops(wallet["balance"]) for wallet in active)),
                                 count=len(active)))
    state["processed"] += count
    state["cursors"]["operations"] = cursor
    state.update(last_success=now, operations_last_run=count, head_ledger=head,
                 lag_ledgers=0 if caught_up else max(0, head - (int(cursor) >> 32)), caught_up=caught_up)
    store.commit(state, events)
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--config", type=Path, default=Path("config.json"))
    args = parser.parse_args()
    cfg = load(args.config)
    store = Store(args.data)
    with store.locked():
        now = utc()
        try:
            state = scan(Horizon(cfg), store, cfg, now)
        except Exception as error:
            path = store.root / "errors" / (now[:10] + ".json")
            errors = load(path, {})
            errors[now] = {"type": type(error).__name__, "message": str(error)[:300]}
            write(path, errors)
            print(f"Scan failed: {error}", file=sys.stderr)
            return 1
        print(json.dumps({field: state[field] for field in
                          ("last_success", "operations_last_run", "lag_ledgers", "caught_up")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
