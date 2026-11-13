"""Integrity check for the hackathon price file.

Usage: python -I check_data.py <path to prices.csv>

Prints structure only (row counts, dates, blanks). It prints no prices and no
returns, so running it does not reveal anything about the held-out period.
"""
import csv
import datetime as dt
import sys

EXPECTED_ROWS = 1255
EXPECTED_FIRST = dt.date(2021, 11, 1)
EXPECTED_LAST = dt.date(2026, 10, 30)
EXPECTED_ASSETS = 14


def main(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    header = rows[0]
    data = [r for r in rows[1:] if any(c.strip() for c in r)]
    dates = [dt.datetime.strptime(r[0], "%m/%d/%Y").date() for r in data]

    problems = []
    if len(data) != EXPECTED_ROWS:
        problems.append(f"row count {len(data)} != {EXPECTED_ROWS}")
    if dates[0] != EXPECTED_FIRST or dates[-1] != EXPECTED_LAST:
        problems.append(f"date range {dates[0]} to {dates[-1]} differs from README")
    if len(header) - 2 != EXPECTED_ASSETS:
        problems.append(f"{len(header) - 2} asset columns, expected {EXPECTED_ASSETS}")
    if dates != sorted(dates):
        problems.append("dates not in order")
    if len(dates) != len(set(dates)):
        problems.append("duplicate dates")
    if any(d.weekday() > 4 for d in dates):
        problems.append("weekend rows present")
    long_gaps = [(a, b) for a, b in zip(dates, dates[1:]) if (b - a).days > 4]
    if long_gaps:
        problems.append(f"gaps over 4 calendar days: {long_gaps}")

    print(f"rows: {len(data)}   range: {dates[0]} to {dates[-1]}")
    print(f"{'column':<10}{'blanks':>8}{'non-positive':>14}{'unchanged days':>16}")
    for j, name in enumerate(header[1:], start=1):
        cells = [r[j].strip() if j < len(r) else "" for r in data]
        blanks = sum(c == "" for c in cells)
        vals = [float(c) for c in cells if c != ""]
        nonpos = sum(v <= 0 for v in vals)
        unchanged = sum(a == b for a, b in zip(vals, vals[1:]))
        print(f"{name[:8]:<10}{blanks:>8}{nonpos:>14}{unchanged:>16}")
        if blanks or nonpos:
            problems.append(f"{name}: {blanks} blanks, {nonpos} non-positive")

    print("\nRESULT:", "OK" if not problems else "PROBLEMS")
    for p in problems:
        print(" -", p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
