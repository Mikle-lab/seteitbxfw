"""Check the persisted scan timestamp for an optional backup dispatch."""
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

from collector.storage import load


def fresh(state, now, maximum_minutes=15):
    recorded = state.get("last_success")
    if not recorded:
        return False
    if state.get("caught_up") is False and state.get("last_operation"):
        recorded = min(recorded, state["last_operation"])
    age = now - datetime.fromisoformat(recorded)
    return timedelta(0) <= age < timedelta(minutes=maximum_minutes)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--minutes", type=int, default=15)
    args = parser.parse_args()
    current = load(Path("data/state.json"), {})
    print("true" if fresh(current, datetime.now(timezone.utc), args.minutes) else "false")
