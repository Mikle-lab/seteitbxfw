"""Compact market views with independent history coverage."""
from collections import defaultdict

from collector.model import stroops, xlm


def market_periods(rows, cuts):
    return {key: [row for row in rows if row["time"] >= cut] for key, cut in cuts.items()}


def sums(rows, directions):
    totals = dict.fromkeys(directions, 0)
    for row in rows:
        key = row.get("direction") or "unknown"
        totals[key] += stroops(row["amount"])
    return totals


def biggest(rows, limit=15):
    return sorted(rows, key=lambda row: (-stroops(row["amount"]), row["id"]))[:limit]


def build_markets(state, labels, wallets, snapshots, flows, fills, cuts, downsample, summaries=None):
    exchanges = {address: label for address, label in labels.items() if label.get("type") == "exchange"}
    balances = [dict(address=address, **label, balance=wallets.get(address, {}).get("balance"),
                     updated=wallets.get(address, {}).get("updated"),
                     history=downsample(sorted(snapshots[address], key=lambda row: row["time"]), 90))
                for address, label in exchanges.items()]
    exchange_periods, dex_periods = {}, {}
    for key, rows in market_periods(flows, cuts).items():
        amounts = sums(rows, ("in", "out"))
        exchange_periods[key] = dict(inflow=xlm(amounts["in"]), outflow=xlm(amounts["out"]),
                                     net=xlm(amounts["in"] - amounts["out"]), count=len(rows),
                                     deposits=biggest([row for row in rows if row["direction"] == "in"]),
                                     withdrawals=biggest([row for row in rows if row["direction"] == "out"]))
    dex_cuts = {key: cut[:16] + ":00Z" for key, cut in cuts.items()}
    detailed = market_periods(fills, cuts)
    for key, rows in market_periods(fills if summaries is None else summaries, dex_cuts).items():
        amounts = sums(rows, ("buy", "sell", "unknown"))
        pairs = defaultdict(lambda: [0, 0])
        daily = defaultdict(lambda: dict(buy=0, sell=0, unknown=0))
        for row in rows:
            units = stroops(row["amount"])
            pair = pairs[(row["code"], row["issuer"])]
            pair[0] += units
            pair[1] += row.get("count", 1)
            daily[row["time"][:10]][row["direction"] or "unknown"] += units
        pair_rows = sorted(pairs.items(), key=lambda item: (-item[1][0], item[0]))[:20]
        dex_periods[key] = dict(**{side: xlm(value) for side, value in amounts.items()},
                                volume=xlm(sum(amounts.values())), count=sum(row.get("count", 1) for row in rows),
                                top=biggest(detailed[key]),
                                pairs=[dict(code=code, issuer=issuer, volume=xlm(value), count=count)
                                       for (code, issuer), (value, count) in pair_rows],
                                history=downsample([dict(day=day, **{side: xlm(value) for side, value in row.items()})
                                                     for day, row in sorted(daily.items())], 90))
    exchange_coverage = state.get("exchange_coverage_from")
    dex_coverage = state.get("dex_coverage_from")
    for key, cutoff in cuts.items():
        exchange_periods[key]["complete"] = bool(exchange_coverage and (key == "all" or exchange_coverage <= cutoff)
                                                 and state.get("caught_up"))
        dex_periods[key]["complete"] = bool(dex_coverage and (key == "all" or dex_coverage <= cutoff)
                                            and state.get("dex_caught_up") and not state.get("dex_error"))
    return dict(exchanges=dict(coverage=exchange_coverage, balances=balances, periods=exchange_periods),
                dex=dict(coverage=dex_coverage, updated=state.get("dex_updated"), error=state.get("dex_error"),
                         caught_up=state.get("dex_caught_up"), periods=dex_periods))
