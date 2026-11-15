"""Strategy variant 6: buy the stocks XLE was forecast to sell, at the rebalance close; short XLE; hold 5 days.

Rules: ../hypothesis-sells-reversal.md (frozen; fingerprints in ../output/frozen_fingerprints.txt).

Usage (from scripts/):
  python -I sells_reversal.py --selftest
  python -I sells_reversal.py design  ../data/prices.csv ../output/forecast_signals.csv
  python -I sells_reversal.py heldout ../data/prices.csv <heldout_forecast_signals.csv>

The design run only reproduces attempt #21 (in-sample). The held-out run is the one that counts;
it refuses to start unless the rules file and this script match their frozen fingerprints.
"""
import csv
import datetime as dt
import hashlib
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

WINDOWS = {"design": (dt.date(2021, 11, 1), dt.date(2024, 10, 31)),
           "heldout": (dt.date(2024, 11, 1), dt.date(2026, 10, 30))}
THRESHOLD_DAYS = 0.25      # forecast sale, in days of 60-day median volume
HOLD = 5                   # trading days after the rebalance close
COST_BPS = 5               # per transaction, 4 per trade
HEDGE = "XLE"
MIN_SIGNALS, MIN_AVG = 6, 0.0040


def load_prices(path, start, end):
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    names = rows[0][1:]
    days, px = [], {n: [] for n in names}
    for r in rows[1:]:
        if not r or not r[0]:
            continue
        d = dt.datetime.strptime(r[0], "%m/%d/%Y").date()
        if d > end:                             # never read past the window
            break
        days.append(d)
        for n, v in zip(names, r[1:]):
            px[n].append(float(v))
    assert days[-1] <= end
    return days, px


def load_signals(path):
    with open(path, newline="") as f:
        return [{"snapshot": dt.date.fromisoformat(r["snapshot_day"]), "rebalance": dt.date.fromisoformat(r["rebalance_day"]),
                 "ticker": r["ticker"], "forecast": float(r["forecast_days"])} for r in csv.DictReader(f)]


def excess(px, t, i0, i1):
    return (px[t][i1] / px[t][i0] - 1) - (px[HEDGE][i1] / px[HEDGE][i0] - 1)


def trades(signals, days, px, window, pick, hold=HOLD):
    """pick(forecast) -> True for a signal. Returns one row per signal whose rebalance is in the window."""
    start, end = window
    idx = {d: i for i, d in enumerate(days)}
    out = []
    for s in signals:
        if not (start <= s["rebalance"] <= end) or not pick(s["forecast"]):
            continue
        reb = idx[s["rebalance"]]
        ex = reb + hold
        assert ex < len(days), "exit falls after the window"
        entry = idx[s["snapshot"]] + 1
        out.append({**s, "move": excess(px, s["ticker"], reb, ex),
                    "stock": px[s["ticker"]][ex] / px[s["ticker"]][reb] - 1,
                    "xle": -(px[HEDGE][ex] / px[HEDGE][reb] - 1),
                    "runup": -excess(px, s["ticker"], entry, reb)})      # signed: positive = fell into the close
    return out


def per_rebalance(tr, cost_bps):
    by = {}
    for t in tr:
        by.setdefault(t["rebalance"], []).append(t["move"] - 4 * cost_bps / 1e4)
    return {e: 0.5 * statistics.mean(v) for e, v in sorted(by.items())}


def summary(tr, cost_bps=COST_BPS):
    if not tr:
        return "no signals"
    m = [t["move"] for t in tr]
    cap = per_rebalance(tr, cost_bps)
    return (f"{len(m)} signals, right {sum(x > 0 for x in m)}/{len(m)}, avg {statistics.mean(m):+.2%} before cost, "
            f"{statistics.mean(m) - 4 * cost_bps / 1e4:+.2%} after; return on capital summed {sum(cap.values()):+.2%}")


def verdict(tr):
    m = [t["move"] for t in tr]
    if len(m) < MIN_SIGNALS:
        return f"TOO FEW TO JUDGE ({len(m)} signals, need {MIN_SIGNALS})"
    ok = statistics.mean(m) >= MIN_AVG and sum(x > 0 for x in m) > len(m) / 2
    return "SUPPORTED" if ok else "NOT SUPPORTED"


def check_fingerprints():
    want = {}
    with open(os.path.join(ROOT, "output", "frozen_fingerprints.txt")) as f:
        for line in f:
            parts = line.split()
            if len(parts) == 2 and len(parts[0]) == 64:
                want[parts[1]] = parts[0]            # later entries win
    for rel in ("hypothesis-sells-reversal.md", "scripts/sells_reversal.py"):
        with open(os.path.join(ROOT, rel), "rb") as f:
            got = hashlib.sha256(f.read()).hexdigest()
        if want.get(rel) != got:
            sys.exit(f"STOP: {rel} does not match its frozen fingerprint; held-out run refused.")
    print("Fingerprints checked OK.")


def run(which, prices_path, signals_path):
    window = WINDOWS[which]
    if which == "heldout":
        check_fingerprints()
    days, px = load_prices(prices_path, *window)
    signals = load_signals(signals_path)
    main = trades(signals, days, px, window, lambda f: f <= -THRESHOLD_DAYS)
    label = "DESIGN PERIOD (in-sample: reproduces attempt #21, not evidence)" if which == "design" else "HELD-OUT PERIOD (single run)"
    print(f"VARIANT 6, sells bounce-back. {label}: {window[0]} to {window[1]}")
    print("Move = stock minus XLE, rebalance close to close 5 trading days later; positive = prediction right.\n")
    print(f"{'rebalance':<12}{'stock':<6}{'forecast':>9}{'move':>8}{'stock':>8}{'-XLE':>8}{'run-up':>8}")
    for t in main:
        print(f"{t['rebalance']!s:<12}{t['ticker']:<6}{t['forecast']:>+8.2f}d{t['move']:>+8.2%}{t['stock']:>+8.2%}{t['xle']:>+8.2%}{t['runup']:>+8.2%}")
    print(f"\nRESULT: {summary(main)}")
    if main:
        print(f"  stock side avg {statistics.mean(t['stock'] for t in main):+.2%}, XLE side avg {statistics.mean(t['xle'] for t in main):+.2%}")
        print("  return on capital per rebalance after costs: "
              + ", ".join(f"{e} {v:+.2%}" for e, v in per_rebalance(main, COST_BPS).items()))
    print(f"  bar (>= {MIN_SIGNALS} signals, avg >= {MIN_AVG:.2%} before cost, right on more than half): {verdict(main)}")

    print("\nDECLARED CHECKS (not results)")
    print(f"  threshold 0.5 days: {summary(trades(signals, days, px, window, lambda f: f <= -0.5))}")
    for h in (1, 3):
        print(f"  hold {h} days: {summary(trades(signals, days, px, window, lambda f: f <= -THRESHOLD_DAYS, h))}")
    for c in (10, 20):
        print(f"  cost {c} bps: {summary(main, c)}")
    print(f"  placebo, forecast sells under 0.25 days: {summary(trades(signals, days, px, window, lambda f: -THRESHOLD_DAYS < f < 0))}")
    mirror = trades(signals, days, px, window, lambda f: f >= THRESHOLD_DAYS)
    for t in mirror:
        t["move"] = -t["move"]                     # fade the fund's buy
    print(f"  mirror, fade forecast buys >= 0.25 days: {summary(mirror)}")


def selftest():
    days = [dt.date(2024, 1, 1) + dt.timedelta(days=k) for k in range(40)]
    px = {"XLE": [100.0] * 40, "AAA": [50.0] * 40, "BBB": [20.0] * 40}
    for k in range(21, 40):
        px["AAA"][k] = 51.0                        # +2% after the rebalance at day 20
        px["XLE"][k] = 100.5                       # XLE +0.5%
    sig = [{"snapshot": days[14], "rebalance": days[20], "ticker": "AAA", "forecast": -0.4},
           {"snapshot": days[14], "rebalance": days[20], "ticker": "BBB", "forecast": -0.1},
           {"snapshot": days[14], "rebalance": days[20], "ticker": "XLE", "forecast": 0.0}]
    win = (days[0], days[30])
    tr = trades(sig, days, px, win, lambda f: f <= -THRESHOLD_DAYS)
    assert [t["ticker"] for t in tr] == ["AAA"], tr
    assert abs(tr[0]["move"] - 0.015) < 1e-12 and abs(tr[0]["stock"] - 0.02) < 1e-12 and abs(tr[0]["xle"] + 0.005) < 1e-12
    cap = per_rebalance(tr, COST_BPS)
    assert abs(cap[days[20]] - 0.5 * (0.015 - 0.002)) < 1e-12
    assert verdict(tr).startswith("TOO FEW")
    assert verdict(tr * 6) == "SUPPORTED"
    print("selftest OK")


if __name__ == "__main__":
    if sys.argv[1] == "--selftest":
        selftest()
    else:
        run(sys.argv[1], sys.argv[2], sys.argv[3])
