"""Calculate the next collector slot without accumulating runner delays."""
import argparse
import time

INTERVAL_SECONDS = 360


def next_slot(seed, now):
    if seed < 1 or seed > now + INTERVAL_SECONDS:
        raise ValueError("Invalid automatic scan slot")
    intervals = max(1, (now - seed) // INTERVAL_SECONDS + 1)
    return seed + intervals * INTERVAL_SECONDS


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("slot", type=int)
    args = parser.parse_args()
    print(next_slot(args.slot, int(time.time())))
