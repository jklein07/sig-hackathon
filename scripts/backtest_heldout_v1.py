"""Held-out run of strategy variant 1 (XLE rebalance: run-up and reversal legs), with the frozen code unchanged.

Usage (from scripts/):
  python -I backtest_heldout_v1.py design  ../data/prices.csv ../output/forecast_signals.csv          wrapper check
  python -I backtest_heldout_v1.py heldout ../data/prices.csv ../output/heldout_forecast_signals.csv  the single run

Every rule and number comes from the frozen scripts/backtest_design.py (build, spread, chance, portfolio, summary,
THRESHOLD_DAYS 0.5, REVERSAL_DAYS 5, COST_BPS 5, the bar). This file only chooses which price rows are loaded:
the design window, or the held-out window 2024-11-01 to 2026-10-30. Random-date draws fall inside the loaded window.

Signals: variant 1's forecast_rebalance.py cannot run on the held-out years (it handles only the Pioneer merger and
reads the next quarter-end). The held-out signals come from forecast_rebalance_v2.py, frozen for variant 6 before
any held-out data was read, which reproduces all 108 design forecasts of v1 to 4 decimals (attempt #25).
The held-out run refuses to start unless this file, backtest_design.py, hypothesis.md and the v2 forecast match
their frozen fingerprints.
"""
import csv
import datetime as dt
import hashlib
import os
import random
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)                    # -I drops the script folder
import backtest_design as bd                # frozen; nothing in it is changed or overridden

WINDOWS = {"design": (dt.date(2021, 11, 1), dt.date(2024, 10, 31)),
           "heldout": (dt.date(2024, 11, 1), dt.date(2026, 10, 30))}
FROZEN = ("hypothesis.md", "scripts/backtest_design.py", "scripts/forecast_rebalance_v2.py", "scripts/backtest_heldout_v1.py")


def check_fingerprints():
    want = {}
    with open(os.path.join(ROOT, "output", "frozen_fingerprints.txt")) as f:
        for ln in f:
            p = ln.split()
            if len(p) == 2 and len(p[0]) == 64:
                want[p[1]] = p[0]
    for rel in FROZEN:
        with open(os.path.join(ROOT, rel), "rb") as f:
            if want.get(rel) != hashlib.sha256(f.read()).hexdigest():
                sys.exit(f"STOP: {rel} does not match its frozen fingerprint; held-out run refused.")
    print("Fingerprints checked OK.")


def load_window(path, start, end):
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    names = rows[0][1:]
    days, px = [], {n: [] for n in names}
    for r in rows[1:]:
        if not r or not r[0]:
            continue
        d = dt.datetime.strptime(r[0], "%m/%d/%Y").date()
        if d < start:
            continue
        if d > end:
            break
        days.append(d)
        for n, v in zip(names, r[1:]):
            px[n].append(float(v))
    assert days[0] >= start and days[-1] <= end
    return days, px


def main(which, prices_path, signals_path):
    if which == "heldout":
        check_fingerprints()
    days, px = load_window(prices_path, *WINDOWS[which])
    with open(signals_path, newline="") as f:
        signals = [{"snapshot": dt.date.fromisoformat(r["snapshot_day"]), "rebalance": dt.date.fromisoformat(r["rebalance_day"]),
                    "ticker": r["ticker"], "forecast": float(r["forecast_days"])} for r in csv.DictReader(f)]
    rng = random.Random(bd.SEED)
    trades = bd.build(signals, days, px, bd.THRESHOLD_DAYS, bd.REVERSAL_DAYS)
    label = "HELD-OUT PERIOD (single run; fourth look at the window)" if which == "heldout" else "DESIGN PERIOD (wrapper check)"
    print(f"VARIANT 1 BACK-TEST, {label} ({days[0]} to {days[-1]}), rules as frozen in hypothesis.md")
    print(f"{len(trades)} signals at {len({t['rebalance'] for t in trades})} of {len({s['rebalance'] for s in signals})} rebalances. "
          "Returns are stock minus XLE, before costs, signed so that positive means the prediction was right.\n")
    print(f"{'rebalance':<12}{'stock':<6}{'forecast':>9}{'fund':>7}{'run-up':>9}{'reversal':>10}")
    for t in trades:
        print(f"{t['rebalance']!s:<12}{t['ticker']:<6}{t['forecast']:>+8.1f}d{'buys' if t['dir'] > 0 else 'sells':>7}"
              f"{t['runup']:>+9.2%}{t['reversal']:>+10.2%}")
    cost_leg = 4 * bd.COST_BPS / 1e4
    print()
    if not trades:
        print("No signals: nothing to test.")
        return
    for leg in ("runup", "reversal"):
        r = [t[leg] for t in trades]
        wrong, avg = sum(x <= 0 for x in r), statistics.mean(r)
        verdict = "SUPPORTED" if wrong <= 1 and avg >= 2 * cost_leg else "NOT SUPPORTED"
        port = bd.portfolio(trades, leg, bd.COST_BPS)
        print(f"{leg.upper()}: right sign on {len(r) - wrong} of {len(r)}; average {avg:+.2%} (median {statistics.median(r):+.2%}); "
              f"after {cost_leg:.2%} cost {avg - cost_leg:+.2%}")
        print(f"  frozen test (at most one wrong sign, average at least {2 * cost_leg:.2%}): {verdict}")
        print(f"  random dates: chance alone did as well in {bd.chance(trades, leg, px, len(days), rng):.1%} of {bd.DRAWS:,} draws")
        print("  return on capital per rebalance after costs: " + ", ".join(f"{e} {v:+.2%}" for e, v in port.items())
              + f"; total {sum(port.values()):+.2%}")
    print("\nDECLARED CHECKS (not results)")
    for c in (10, 20):
        print(f"  cost {c} bps: {bd.summary(trades, c)}")
    for th in (0.25, 1.0):
        alt = bd.build(signals, days, px, th, bd.REVERSAL_DAYS)
        print(f"  threshold {th} days ({len(alt)} signals): {bd.summary(alt) if alt else 'no signals'}")
    for w in (3, 10):
        alt = bd.build(signals, days, px, bd.THRESHOLD_DAYS, w)
        r = [t["reversal"] for t in alt]
        print(f"  reversal window {w} days: right sign {sum(x > 0 for x in r)}/{len(r)}, average {statistics.mean(r):+.2%}")
    plc = bd.build(signals, days, px, bd.THRESHOLD_DAYS, bd.REVERSAL_DAYS, placebo=True)
    print(f"  placebo, forecast under {bd.PLACEBO_BELOW} days ({len(plc)} stock-quarters): "
          + "; ".join(f"{leg} right sign {sum(t[leg] > 0 for t in plc)}/{len(plc)}, average {statistics.mean(t[leg] for t in plc):+.2%}"
                      for leg in ("runup", "reversal")))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
