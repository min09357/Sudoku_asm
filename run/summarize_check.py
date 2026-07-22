#!/usr/bin/env python3
"""Summarize a watch_refreshes check-mode log.

The log holds two header lines naming the constraints, then a CSV table:
    diff_functions,<hex>,...
    same_functions,<hex>,...
    idx,fpaddr,spaddr,avg,med,min,max

Each row is one address pair. `avg` is the mean refresh interval in TSC cycles.
A pair whose two addresses sit in different refresh domains sees both ranks'
refresh streams merged, so its interval is roughly halved.

Usage:
    ./summarize_check.py LOG [LOG ...] [-t THRESHOLD]
"""

import argparse
import statistics
import sys

# Matches REGULAR_REFRESH_INTERVAL_THRESHOLD_ in the platform header.
DEFAULT_THRESHOLD = 14000


def ReadLog(path):
    """Return (diff, same, avgs) from a check-mode log."""
    diff = same = ""
    avgs = []
    header = None
    with open(path) as f:
        for line in f:
            line = line.rstrip("\n")
            if line.startswith("diff_functions,"):
                diff = line.split(",", 1)[1].strip(",")
            elif line.startswith("same_functions,"):
                same = line.split(",", 1)[1].strip(",")
            elif line.startswith("idx,"):
                header = line.split(",")
            elif header:
                fields = line.split(",")
                if len(fields) == len(header):
                    avgs.append(int(fields[header.index("avg")]))
    return diff, same, avgs


def Report(path, threshold):
    try:
        diff, same, avgs = ReadLog(path)
    except OSError as e:
        print(f"    {e}", file=sys.stderr)
        return
    if not avgs:
        print(f"    {path}: no samples")
        return

    reduced = sum(1 for x in avgs if threshold > x > 1000)
    pct = 100.0 * reduced / len(avgs)
    verdict = "DOMAIN CHANGES" if pct > 90 else (
        "BANK DIRECTION" if pct < 10 else "MIXED -- inspect the log")

    print(f"    diff: {diff}")
    print(f"    samples {len(avgs)}  mean {int(statistics.mean(avgs))}  "
          f"median {int(statistics.median(avgs))}")
    print(f"    below threshold ({threshold}): {reduced} ({pct:.1f}%)  -> {verdict}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("logs", nargs="+")
    parser.add_argument("-t", "--threshold", type=int, default=DEFAULT_THRESHOLD)
    args = parser.parse_args()
    for path in args.logs:
        Report(path, args.threshold)


if __name__ == "__main__":
    main()
