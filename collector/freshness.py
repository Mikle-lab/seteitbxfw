"""Check the persisted scan timestamp for an optional backup dispatch."""
from datetime import datetime, timedelta, timezone
from pathlib import Path

from collector.storage import load


def fresh(state, now, maximum_minutes=15):
    recorded = state.get("last_success")
    if not recorded:
        return False
    age = now - datetime.fromisoformat(recorded)
    return timedelta(0) <= age < timedelta(minutes=maximum_minutes)


if __name__ == "__main__":
    current = load(Path("data/state.json"), {})
    print("true" if fresh(current, datetime.now(timezone.utc)) else "false")
