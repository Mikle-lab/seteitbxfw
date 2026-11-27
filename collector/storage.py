"""Crash-safe state commit with a replayable journal and UTC daily archives."""
import fcntl
import json
import os
from contextlib import contextmanager
from pathlib import Path


def load(path, default=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    with temp.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    temp.replace(path)
    sync_directory(path.parent)


def sync_directory(path):
    descriptor = os.open(path, os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


class Store:
    def __init__(self, root):
        self.root = Path(root)
        self.state = self.root / "state.json"
        self.journal = self.root / "pending.json"

    @contextmanager
    def locked(self):
        self.root.mkdir(parents=True, exist_ok=True)
        with (self.root / ".lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.recover()
            yield

    def recover(self):
        pending = load(self.journal)
        if pending is None:
            return
        for day, items in pending["days"].items():
            path = self.root / "archive" / (day + ".json")
            archive = load(path, {})
            for key, rows in items.items():
                archive.setdefault(key, {}).update(rows)
            write(path, archive)
        write(self.state, pending["state"])
        self.journal.unlink()
        sync_directory(self.root)

    def commit(self, state, events):
        days = {}
        for key, rows in events.items():
            for row in rows:
                days.setdefault(row["time"][:10], {}).setdefault(key, {})[row["id"]] = row
        write(self.journal, {"state": state, "days": days})
        self.recover()
