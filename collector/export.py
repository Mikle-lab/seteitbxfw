"""Build a compact Pages artifact from the versioned collector data."""
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from collector.analytics.activity import direct_interactions, inactivity
from collector.analytics.trends import build_trends
from collector.market_export import build_markets
from collector.services.prices import SOURCE, price_history
from collector.model import stroops, valid_address, xlm
from collector.storage import load, write

PERIODS = {"1h": 1, "24h": 24, "7d": 168, "30d": 720, "90d": 2160, "all": None}


def timestamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def ordered(rows):
    return sorted(rows, key=lambda row: (row["time"], row["id"]))


def downsample(rows, maximum):
    if len(rows) <= maximum:
        return rows
    return [rows[index * (len(rows) - 1) // (maximum - 1)] for index in range(maximum)]


def build(data=Path("data"), target=Path("dist")):
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree("web", target)
    (target / ".nojekyll").touch()
    public = target / "data"
    state = load(data / "state.json", {})
    cfg = load(Path("config.json"))
    end = timestamp(state["last_success"]) if state else datetime.now(timezone.utc)
    coverage = timestamp(state["coverage_from"]) if state else None
    errors = sorted((data / "errors").glob("*.json"))
    last_error = None
    if errors:
        details = load(errors[-1], {})
        if details:
            last_error = max(details)
    operations, signals, totals, flows, fills, fill_totals = [], [], [], [], [], []
    prices = []
    snapshots = defaultdict(list)
    config_labels = cfg["labels"]
    wallets = state.get("wallets", {})
    for path in sorted((data / "archive").glob("*.json")):
        day = load(path)
        operations.extend(day.get("operations", {}).values())
        signals.extend(day.get("signals", {}).values())
        totals.extend(day.get("totals", {}).values())
        flows.extend(day.get("exchange", {}).values())
        prices.extend(day.get("prices", {}).values())
        day_fills = list(day.get("trades", {}).values())
        fills.extend(day_fills)
        fill_totals.extend(day.get("trade_summaries", {}).values() if "trade_summaries" in day else day_fills)
        for row in day.get("snapshots", {}).values():
            snapshots[row["address"]].append(row)
    operations, signals, totals = map(ordered, (operations, signals, totals))
    by_wallet, signals_by_wallet = defaultdict(list), defaultdict(list)
    for row in operations:
        for address in {row["sender"], row["recipient"]} & wallets.keys():
            by_wallet[address].append(row)
    for row in signals:
        if row["address"] in wallets:
            signals_by_wallet[row["address"]].append(row)

    cuts = {key: (end - timedelta(hours=hours) if hours else coverage or end).isoformat().replace("+00:00", "Z")
            for key, hours in PERIODS.items()}
    trend_periods, wallet_trends = build_trends(wallets, snapshots, end.date())
    price_rows = price_history(prices)
    prices_by_day = {row["day"]: row for row in price_rows}
    write(public / "trends.json", dict(through=(end.date() - timedelta(days=1)).isoformat(), periods=trend_periods,
                                       prices=price_rows[-30:], price_source=SOURCE, price_error=state.get("price_error")))
    threshold_days = cfg.get("inactive_days", 30)
    activity_through = state.get("last_operation")
    interactions = direct_interactions(operations, wallets, cuts["30d"])
    links_by_address = defaultdict(list)
    for interaction in interactions:
        for address in (interaction["left"], interaction["right"]):
            links_by_address[address].append(interaction)
    write(public / "interactions.json", dict(through=activity_through, pairs=interactions[:100],
                                             coverage=state.get("coverage_from"), total=len(interactions)))
    metrics = {}
    whale_rows = []
    for address, wallet in wallets.items():
        if not valid_address(address):
            continue
        samples = ordered(snapshots[address])
        history = downsample(samples, 240)
        stats = {}
        related = by_wallet[address]
        counterparts = Counter()
        for row in related:
            other = row["sender"] if row["recipient"] == address else row["recipient"]
            if other:
                counterparts[other] += 1
        for period, cut in cuts.items():
            observed = [row for row in samples if row["delta"] is not None and row["previous_time"] >= cut]
            movements = [row for row in related if row["time"] >= cut]
            received = sum(stroops(row["amount"]) for row in movements if row["recipient"] == address)
            sent = sum(stroops(row["amount"]) for row in movements if row["sender"] == address)
            up = sum(max(0, stroops(row["delta"])) for row in observed)
            down = sum(max(0, -stroops(row["delta"])) for row in observed)
            baseline = stroops(observed[0]["balance"]) - stroops(observed[0]["delta"]) if observed else None
            stats[period] = dict(up=xlm(up), down=xlm(down), delta=xlm(up - down) if observed else None,
                                 percent=float(round(Decimal(up - down) * 100 / baseline, 2)) if baseline else None,
                                 received=xlm(received), sent=xlm(sent), operations=len(movements),
                                 anomalies=sum(row["time"] >= cut for row in signals_by_wallet[address]))
        for interval in wallet_trends[address].values():
            for row in interval["daily"]:
                row["price"] = prices_by_day.get(row["day"])
        whale_row = dict(address=address, **wallet, periods=stats, inactivity=inactivity(wallet, activity_through, threshold_days))
        whale_rows.append(whale_row)
        write(public / "wallets" / (address + ".json"), dict(wallet=whale_row, history=history,
              trends=wallet_trends[address], operations=related[-100:][::-1], anomalies=signals_by_wallet[address][-100:][::-1],
              counterparts=counterparts.most_common(12), interactions=links_by_address[address][:15]))

    whales = [row for row in whale_rows if not row["label"]]
    active = [row for row in whales if row["active"]]
    for period, cut in cuts.items():
        up = sum(stroops(row["periods"][period]["up"]) for row in whales)
        down = sum(stroops(row["periods"][period]["down"]) for row in whales)
        metrics[period] = dict(up=xlm(up), down=xlm(down), net=xlm(up - down),
                               large=sum(row["time"] >= cut for row in operations),
                               new=sum(row["kind"] == "new" and row["time"] >= cut for row in signals),
                               anomalies=sum(row["time"] >= cut for row in signals),
                               complete=bool(coverage and coverage <= timestamp(cut)),
                               chart=downsample([row for row in totals if row["time"] >= cut], 120))
    markets = build_markets(state, config_labels, wallets, snapshots, flows, fills, cuts, downsample, fill_totals)
    for period in metrics:
        exchange = markets["exchanges"]["periods"][period]
        dex = markets["dex"]["periods"][period]
        metrics[period]["markets"] = dict(inflow=exchange["inflow"] if markets["exchanges"]["coverage"] else None,
                                          outflow=exchange["outflow"] if markets["exchanges"]["coverage"] else None,
                                          buy=dex["buy"] if markets["dex"]["coverage"] else None,
                                          sell=dex["sell"] if markets["dex"]["coverage"] else None)
    write(public / "markets.json", markets)
    indexed = sorted(whale_rows, key=lambda row: stroops(row["balance"]), reverse=True)
    write(public / "summary.json", dict(schema=1, updated=state.get("last_success"), error=last_error,
          last_trigger=state.get("last_trigger"), scheduled=state.get("last_scheduled_success"),
          fallback=state.get("last_fallback_success"),
          coverage=state.get("coverage_from"), lag=state.get("lag_ledgers"), caught_up=state.get("caught_up"),
          processed=state.get("processed", 0), processed_last=state.get("operations_last_run", 0),
          exported=end.isoformat(), active=len(active), discovered=len(whales),
          total=xlm(sum(stroops(row["balance"]) for row in active)), periods=metrics,
          categories=Counter(row["category"] for row in active), labels=config_labels,
          inactive_days=threshold_days,
          threshold=cfg["large_xlm"], sections={"operations": export_chunks(public, "operations", operations),
                                              "anomalies": export_chunks(public, "anomalies", signals)}))
    write(public / "whales.json", indexed)


def export_chunks(root, name, rows):
    days = defaultdict(list)
    for row in reversed(rows):
        days[row["time"][:10]].append(row)
    manifest = []
    for day, records in sorted(days.items(), reverse=True):
        for start in range(0, len(records), 250):
            path = f"{name}/{day}-{start // 250}.json"
            write(root / path, records[start:start + 250])
            manifest.append({"path": path, "day": day, "count": len(records[start:start + 250])})
    return manifest


if __name__ == "__main__":
    build()
