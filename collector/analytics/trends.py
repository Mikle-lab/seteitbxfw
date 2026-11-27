"""UTC balance trends and robust per-wallet anomaly baselines."""
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from statistics import median_low

from collector.analytics.signals import record
from collector.model import stroops, xlm
from collector.storage import load

DAY = timedelta(days=1)
CLOSE_GRACE = timedelta(hours=3)
BASELINE_DAYS = 14
MIN_BASELINE = 7
WINDOWS = {"7d": 7, "30d": 30}


def time_of(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def daily_changes(samples):
    """Use the closest eligible observation before each UTC midnight."""
    closes = {}

    def observe(text, amount):
        instant = time_of(text)
        day = instant.date()
        midnight = datetime.combine(day + DAY, datetime.min.time(), timezone.utc)
        if midnight - instant <= CLOSE_GRACE and (day not in closes or instant > closes[day][0]):
            closes[day] = (instant, amount)

    for row in samples:
        balance = stroops(row["balance"])
        observe(row["time"], balance)
        if row.get("previous_time") and row.get("delta") is not None:
            observe(row["previous_time"], balance - stroops(row["delta"]))

    return {day: balance - closes[day - DAY][1] for day, (_, balance) in closes.items() if day - DAY in closes}


def trend(changes, today, days):
    start = today - timedelta(days=days)
    selected = [(day, value) for day, value in sorted(changes.items()) if start <= day < today]
    received = sum(max(0, change) for _, change in selected)
    reduced = sum(max(0, -change) for _, change in selected)
    return dict(observed=len(selected), required=days, up=xlm(received) if selected else None,
                down=xlm(reduced) if selected else None, net=xlm(received - reduced) if selected else None,
                daily=[dict(day=day.isoformat(), delta=xlm(change)) for day, change in selected])


def anomaly_for_day(address, changes, target, minimum):
    observed = changes.get(target)
    if observed is None or abs(observed) < minimum:
        return None
    baseline = [change for day, change in changes.items()
                if target - timedelta(days=BASELINE_DAYS) <= day < target]
    if len(baseline) < MIN_BASELINE:
        return None
    median = median_low(baseline)
    mad = median_low(abs(change - median) for change in baseline)
    distance = abs(observed - median)
    if distance < max(minimum, 6 * mad):
        return None
    direction = "увеличение" if observed > 0 else "сокращение"
    level = "high" if distance >= max(5 * minimum, 12 * mad) else "medium"
    return record(f"daily:{target}:{address}", "daily_outlier", level,
                  f"Нетипичное {direction} баланса за {target} UTC. Медиана {xlm(median)} XLM по {len(baseline)} дням.",
                  target.isoformat() + "T23:59:59Z", address, observed)


def closed_day_signals(state, store, snapshots, now, minimum):
    instant = time_of(now)
    # Allow rotating balance checks after midnight to contribute a prior close.
    cutoff = (instant - CLOSE_GRACE).date() - DAY
    previous = state.get("trends_evaluated_through")
    start = date.fromisoformat(previous) + DAY if previous else cutoff
    if start > cutoff:
        return []
    first = start - timedelta(days=BASELINE_DAYS + 1)
    samples = defaultdict(list)
    for path in sorted((store.root / "archive").glob("*.json")):
        if first.isoformat() <= path.stem <= instant.date().isoformat():
            daily = load(path, {})
            for row in daily.get("snapshots", {}).values():
                samples[row["address"]].append(row)
    for row in snapshots:
        samples[row["address"]].append(row)

    result = []
    for address, points in samples.items():
        if state["wallets"].get(address, {}).get("label"):
            continue
        changes = daily_changes(points)
        for target in sorted(day for day in changes if start <= day <= cutoff):
            signal = anomaly_for_day(address, changes, target, minimum)
            if signal:
                result.append(signal)
    state["trends_evaluated_through"] = cutoff.isoformat()
    return result


def build_trends(wallets, snapshots, today):
    periods = {}
    individual = {}
    for address in wallets:
        changes = daily_changes(snapshots[address])
        individual[address] = {key: trend(changes, today, days) for key, days in WINDOWS.items()}
    for key, days in WINDOWS.items():
        rows = []
        for address, values in individual.items():
            wallet = wallets[address]
            if wallet.get("label"):
                continue
            stats = values[key]
            rows.append(dict(address=address, category=wallet["category"], **stats))
        complete = [row for row in rows if row["observed"] == days]
        reported = sum(row["observed"] > 0 for row in rows)
        periods[key] = dict(required=days, complete=len(complete), observed=reported, total=len(rows),
                            accumulation=sorted([row for row in complete if stroops(row["net"]) > 0],
                                                key=lambda row: (-stroops(row["net"]), row["address"]))[:15],
                            reduction=sorted([row for row in complete if stroops(row["net"]) < 0],
                                             key=lambda row: (stroops(row["net"]), row["address"]))[:15])
    return periods, individual
