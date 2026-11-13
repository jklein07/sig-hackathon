"""Build the design-period event calendar and fetch what the forecast needs on each snapshot day.

Usage: python -I fetch_snapshot_inputs.py <prices.csv> <out_dir>

Writes three files into <out_dir>:
  calendar_design.csv            snapshot day, rebalance day, rule version, quarter-ends before and after
  snapshot_day_closes.csv        unadjusted closing price of every index member on each snapshot day
  snapshot_day_volume_60d.csv    median daily volume (million shares) over the 60 trading days ending on the snapshot day

Only the snapshot-day close and the trailing volume are kept. No returns are computed.
Prices come from Yahoo's public chart endpoint. The hackathon price file cannot be used
for company sizes because its prices are adjusted for dividends.
"""
import csv
import datetime as dt
import json
import statistics
import sys
import time
import urllib.request

DESIGN_END = dt.date(2024, 10, 31)
REBALANCE_MONTHS = [(2021, 12)] + [(y, m) for y in (2022, 2023, 2024) for m in (3, 6, 9, 12)]
NEW_RULE_FROM = dt.date(2024, 9, 20)      # rebalance effective after this close uses the new trimming method
MEMBERS = ["XOM", "CVX", "COP", "EOG", "OXY", "SLB", "MPC", "PSX", "VLO", "PXD", "WMB", "KMI", "OKE", "HES",
           "DVN", "HAL", "BKR", "FANG", "MRO", "CTRA", "APA", "EQT", "TRGP"]
TRADABLE = ["XOM", "CVX", "COP", "EOG", "OXY", "SLB", "MPC", "PSX", "VLO"]


def nth_friday(year, month, n):
    first = dt.date(year, month, 1)
    return first + dt.timedelta(days=(4 - first.weekday()) % 7 + 7 * (n - 1))


def quarter_end(d, shift):
    """Quarter-end strictly before d (shift=-1) or on/after d (shift=0)."""
    ends = [dt.date(y, m, 30 if m in (6, 9) else 31) for y in range(2021, 2026) for m in (3, 6, 9, 12)]
    before = [e for e in ends if e < d]
    after = [e for e in ends if e >= d]
    return before[-1] if shift < 0 else after[0]


def fetch(ticker):
    p1 = int(dt.datetime(2021, 6, 1).timestamp())
    p2 = int(dt.datetime(DESIGN_END.year, DESIGN_END.month, DESIGN_END.day, 23).timestamp())
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?period1={p1}&period2={p2}&interval=1d&events=split"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        res = json.load(r)["chart"]["result"][0]
    q = res["indicators"]["quote"][0]
    days = [dt.datetime.fromtimestamp(t, dt.timezone.utc).date() for t in res["timestamp"]]
    splits = list(res.get("events", {}).get("splits", {}).values())
    return days, q["close"], q["volume"], splits


def main(prices_path, out_dir):
    with open(prices_path, newline="", encoding="utf-8-sig") as f:
        trading_days = {dt.datetime.strptime(r[0], "%m/%d/%Y").date() for r in list(csv.reader(f))[1:] if r and r[0]}

    events = []
    for y, m in REBALANCE_MONTHS:
        eff, ref = nth_friday(y, m, 3), nth_friday(y, m, 2)
        if eff > DESIGN_END:
            continue
        for label, d in (("snapshot", ref), ("rebalance", eff)):
            if d not in trading_days:
                print(f"WARNING: {label} day {d} is not a trading day in the price file")
        events.append((ref, eff, "new" if eff >= NEW_RULE_FROM else "old", quarter_end(eff, -1), quarter_end(eff, 0)))
    with open(f"{out_dir}/calendar_design.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["snapshot_day", "rebalance_day", "rule", "quarter_end_before", "quarter_end_after"])
        w.writerows(events)
    print(f"calendar: {len(events)} rebalances, {events[0][1]} to {events[-1][1]}")

    refs = [e[0] for e in events]
    closes, volumes = {}, {}
    for t in MEMBERS:
        try:
            days, close, volume, splits = fetch(t)
        except Exception as exc:  # delisted tickers may be missing
            print(f"{t}: FAILED ({exc})")
            continue
        if splits:
            print(f"{t}: splits in the data {splits}")
        idx = {d: i for i, d in enumerate(days)}
        closes[t] = [round(close[idx[r]], 4) if r in idx and close[idx[r]] else "" for r in refs]
        if t in TRADABLE:
            volumes[t] = []
            for r in refs:
                window = [v for v in volume[max(0, idx[r] - 59): idx[r] + 1] if v]
                volumes[t].append(round(statistics.median(window) / 1e6, 3))
        missing = [str(r) for r, c in zip(refs, closes[t]) if c == ""]
        print(f"{t}: {days[0]} to {days[-1]}" + (f"  no price on {missing}" if missing else ""))
        time.sleep(0.5)

    for name, table in (("snapshot_day_closes.csv", closes), ("snapshot_day_volume_60d.csv", volumes)):
        with open(f"{out_dir}/{name}", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["ticker"] + [str(r) for r in refs])
            for t, row in table.items():
                w.writerow([t] + row)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
