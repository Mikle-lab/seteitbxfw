"""Comparable balance measurements for the private-holder overview."""
from bisect import bisect_right
from datetime import datetime, timedelta

from collector.analytics.review import approved
from collector.model import stroops, valid_address, xlm

MAX_SAMPLE_AGE = timedelta(hours=3)


def instant(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def utc_string(value):
    return value.isoformat().replace("+00:00", "Z") if value is not None else None


def measurements(rows, wallet):
    points = {}
    # The prior timestamp identifies a real successful lookup, even when an
    # unchanged balance did not result in a separate archived snapshot.
    for row in rows:
        if row.get("previous_time") and row.get("delta") is not None:
            points.setdefault(instant(row["previous_time"]), stroops(row["balance"]) - stroops(row["delta"]))
    for row in rows:
        points[instant(row["time"])] = stroops(row["balance"])
    if wallet.get("updated") and wallet.get("balance") is not None:
        points[instant(wallet["updated"])] = stroops(wallet["balance"])
    return sorted(points.items())


def private_balance_periods(config, wallets, snapshots, end, periods):
    registry = config.get("private_review") or {}
    eligible = sorted(address for address in registry if valid_address(address) and approved(address, config))
    series = {}
    for address in eligible:
        samples = [(time, balance) for time, balance in measurements(snapshots.get(address, ()), wallets.get(address, {}))
                   if time <= end]
        if samples:
            times, balances = zip(*samples)
            series[address] = times, balances
    all_start = min((times[0] for times, _ in series.values()), default=end)
    return {period: compare(eligible, series, end - timedelta(hours=hours) if hours else all_start, end)
            for period, hours in periods.items()}


def compare(eligible, series, start, end):
    max_age = min(MAX_SAMPLE_AGE, (end - start) / 2)
    changes = {}
    ending_samples = []
    for address, (times, balances) in series.items():
        before = bisect_right(times, start) - 1
        after = bisect_right(times, end) - 1
        if before < 0 or after <= before or start - times[before] > max_age or end - times[after] > max_age:
            continue
        changes[address] = balances[after] - balances[before]
        ending_samples.append(times[after])

    measured = len(changes)
    if not eligible:
        status = "no_holders"
    elif not measured:
        status = "insufficient"
    else:
        status = "complete" if measured == len(eligible) else "partial"
    largest = max(changes, key=lambda address: abs(changes[address]), default=None)
    return dict(status=status, approved=len(eligible), measured=measured, window_start=utc_string(start),
                window_end=utc_string(end), max_sample_age_seconds=int(max_age.total_seconds()),
                observed_through=utc_string(min(ending_samples, default=None)),
                net=xlm(sum(changes.values())) if measured else None,
                increased=sum(delta > 0 for delta in changes.values()) if measured else None,
                decreased=sum(delta < 0 for delta in changes.values()) if measured else None,
                largest=dict(address=largest, delta=xlm(changes[largest])) if largest and changes[largest] else None)
