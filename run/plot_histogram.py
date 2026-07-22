#!/usr/bin/env python3
"""Plot a histogram of the `avg` column of Sudoku memory access logs.

The logs are CSV files whose header is one of:
    idx,paddr,avg,med,min,max                 (single access)
    idx,fpaddr,spaddr,avg,med,min,max         (paired access)

Usage:
    ./plot_histogram.py LOG [LOG ...] [-b BINS] [-o OUTPUT]
"""

import argparse
import csv
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator

# X axis tick spacing in cycles.
MAJOR_TICK = 50
MINOR_TICK = 10


def ReadAverages(path):
    """Read the `avg` column out of a log file."""
    values = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None or "avg" not in reader.fieldnames:
            raise ValueError(f"no 'avg' column in {path}")
        for row in reader:
            raw = row.get("avg")
            if raw is None:
                continue
            raw = raw.strip()
            if not raw:
                continue
            try:
                values.append(float(raw))
            except ValueError:
                # Skip malformed lines (e.g. a truncated final line).
                continue
    return values


def PlotHistogram(path, bins, output):
    values = ReadAverages(path)
    if not values:
        print(f"[-] {path}: no samples, skipped", file=sys.stderr)
        return None

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(values, bins=bins, color="#4c72b0", edgecolor="white", linewidth=0.5)
    ax.set_xlabel("Average access latency (cycles)")
    ax.set_ylabel("Count")
    ax.set_title(os.path.basename(path))

    ax.xaxis.set_major_locator(MultipleLocator(MAJOR_TICK))
    ax.xaxis.set_minor_locator(MultipleLocator(MINOR_TICK))
    ax.tick_params(axis="x", which="major", labelsize=8, rotation=90)
    ax.grid(axis="y", alpha=0.3)
    ax.grid(axis="x", which="major", alpha=0.3)
    ax.grid(axis="x", which="minor", alpha=0.12)

    mean = sum(values) / len(values)
    ax.axvline(mean, color="#c44e52", linestyle="--", linewidth=1.2)
    ax.annotate(
        f"n={len(values)}\nmean={mean:.1f}\nmin={min(values):.0f}\nmax={max(values):.0f}",
        xy=(0.98, 0.95),
        xycoords="axes fraction",
        ha="right",
        va="top",
        fontsize=9,
        bbox=dict(boxstyle="round", facecolor="white", alpha=0.8),
    )

    fig.tight_layout()
    fig.savefig(output, dpi=150)
    plt.close(fig)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("logs", nargs="+", help="log file(s) to plot")
    parser.add_argument("-b", "--bins", default="auto",
                        help="number of histogram bins (default: auto)")
    parser.add_argument("-o", "--output",
                        help="output PNG path (only with a single log file; "
                             "default: <log>.hist.png)")
    args = parser.parse_args()

    if args.output and len(args.logs) > 1:
        parser.error("--output can only be used with a single log file")

    bins = args.bins
    if bins != "auto":
        bins = int(bins)

    for path in args.logs:
        if not os.path.isfile(path):
            print(f"[-] {path}: not found, skipped", file=sys.stderr)
            continue
        output = args.output or f"{path}.hist.png"
        try:
            saved = PlotHistogram(path, bins, output)
        except ValueError as e:
            print(f"[-] {e}", file=sys.stderr)
            continue
        if saved:
            print(f"[+] {saved}")


if __name__ == "__main__":
    main()
