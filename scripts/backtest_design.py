"""Back-test of the frozen hypothesis (hypothesis.md) on the DESIGN period only.

Usage: python -I backtest_design.py <prices.csv> <forecast_signals.csv>

Rows after DESIGN_END are never read. Every number that defines the strategy is a
constant below and matches hypothesis.md; the declared checks vary one of them at a time.
"""
import csv
import datetime as dt
import random
import statistics
import sys

DESIGN_END = dt.date(2024, 10, 31)
THRESHOLD_DAYS = 0.5       # forecast trade, in days of normal volume
REVERSAL_DAYS = 5          # trading days held after the rebalance close
COST_BPS = 5               # per transaction; four transactions per leg
HEDGE = "XLE"
PLACEBO_BELOW = 0.25
DRAWS, SEED = 10_000, 20261113


def load_prices(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    names = rows[0][1:]
    days, px = [], {n: [] for n in names}
    for r in rows[1:]:
        if not r or not r[0]:
            continue
        d = dt.datetime.strptime(r[0], "%m/%d/%Y").date()
        if d > DESIGN_END:
            break
        days.append(d)
        for n, v in zip(names, r[1:]):
            px[n].append(float(v))
    return days, px


def spread(px, t, i0, i1):
    """Stock return minus XLE return from the close of day i0 to the close of day i1."""
    return (px[t][i1] / px[t][i0] - 1) - (px[HEDGE][i1] / px[HEDGE][i0] - 1)


def build(signals, days, px, threshold, reversal_days, placebo=False):
    idx = {d: i for i, d in enumerate(days)}
    out = []
    for s in signals:
        f = s["forecast"]
        if (abs(f) >= PLACEBO_BELOW) if placebo else (abs(f) < threshold):
            continue
        if placebo and f == 0:
            continue
        direction = 1 if f > 0 else -1
        entry, reb = idx[s["snapshot"]] + 1, idx[s["rebalance"]]
        out.append({**s, "dir": direction, "entry": entry, "reb": reb, "exit": reb + reversal_days,
                    "runup": direction * spread(px, s["ticker"], entry, reb),
                    "reversal": -direction * spread(px, s["ticker"], reb, reb + reversal_days)})
    return out


def chance(trades, leg, px, n_days, rng):
    """Share of random-date draws whose average is at least the observed average."""
    observed = statistics.mean(t[leg] for t in trades)
    count = 0
    for _ in range(DRAWS):
        total = 0.0
        for t in trades:
            length = (t["reb"] - t["entry"]) if leg == "runup" else (t["exit"] - t["reb"])
            start = rng.randrange(0, n_days - length)
            sign = t["dir"] if leg == "runup" else -t["dir"]
            total += sign * spread(px, t["ticker"], start, start + length)
        count += total / len(trades) >= observed
    return count / DRAWS


def portfolio(trades, leg, cost_bps):
    """Return on capital per rebalance: capital split equally across signals, half long and half short."""
    by_event = {}
    for t in trades:
        by_event.setdefault(t["rebalance"], []).append(t[leg] - 4 * cost_bps / 1e4)
    return {e: 0.5 * statistics.mean(v) for e, v in sorted(by_event.items())}


def summary(trades, cost_bps=COST_BPS):
    parts = []
    for leg in ("runup", "reversal"):
        r = [t[leg] for t in trades]
        total = sum(portfolio(trades, leg, cost_bps).values())
        parts.append(f"{leg}: right sign {sum(x > 0 for x in r)}/{len(r)}, average {statistics.mean(r):+.2%}, "
                     f"return on capital after costs {total:+.2%}")
    return "; ".join(parts)


def main(prices_path, signals_path):
    days, px = load_prices(prices_path)
    with open(signals_path, newline="") as f:
        signals = [{"snapshot": dt.date.fromisoformat(r["snapshot_day"]), "rebalance": dt.date.fromisoformat(r["rebalance_day"]),
                    "ticker": r["ticker"], "forecast": float(r["forecast_days"])} for r in csv.DictReader(f)]
    rng = random.Random(SEED)
    trades = build(signals, days, px, THRESHOLD_DAYS, REVERSAL_DAYS)

    print(f"BACK-TEST, DESIGN PERIOD ONLY ({days[0]} to {days[-1]}), rules as frozen in hypothesis.md")
    print(f"{len(trades)} signals at {len({t['rebalance'] for t in trades})} of {len({s['rebalance'] for s in signals})} rebalances. "
          "Returns are stock minus XLE, before costs, signed so that positive means the prediction was right.\n")
    print(f"{'rebalance':<12}{'stock':<6}{'forecast':>9}{'fund':>7}{'run-up':>9}{'reversal':>10}")
    for t in trades:
        print(f"{t['rebalance']!s:<12}{t['ticker']:<6}{t['forecast']:>+8.1f}d{'buys' if t['dir'] > 0 else 'sells':>7}"
              f"{t['runup']:>+9.2%}{t['reversal']:>+10.2%}")

    cost_leg = 4 * COST_BPS / 1e4
    print()
    for leg in ("runup", "reversal"):
        r = [t[leg] for t in trades]
        wrong, avg = sum(x <= 0 for x in r), statistics.mean(r)
        verdict = "SUPPORTED" if wrong <= 1 and avg >= 2 * cost_leg else "NOT SUPPORTED"
        port = portfolio(trades, leg, COST_BPS)
        print(f"{leg.upper()}: right sign on {len(r) - wrong} of {len(r)}; average {avg:+.2%} (median {statistics.median(r):+.2%}); "
              f"after {cost_leg:.2%} cost {avg - cost_leg:+.2%}")
        print(f"  frozen test (at most one wrong sign, average at least {2 * cost_leg:.2%}): {verdict}")
        print(f"  random dates: chance alone did as well in {chance(trades, leg, px, len(days), rng):.1%} of {DRAWS:,} draws")
        print("  return on capital per rebalance after costs: " + ", ".join(f"{e} {v:+.2%}" for e, v in port.items())
              + f"; total {sum(port.values()):+.2%}")

    print("\nDECLARED CHECKS (not results)")
    for c in (10, 20):
        print(f"  cost {c} bps: {summary(trades, c)}")
    for th in (0.25, 1.0):
        alt = build(signals, days, px, th, REVERSAL_DAYS)
        print(f"  threshold {th} days ({len(alt)} signals): {summary(alt)}")
    for w in (3, 10):
        alt = build(signals, days, px, THRESHOLD_DAYS, w)
        r = [t["reversal"] for t in alt]
        print(f"  reversal window {w} days: right sign {sum(x > 0 for x in r)}/{len(r)}, average {statistics.mean(r):+.2%}")
    plc = build(signals, days, px, THRESHOLD_DAYS, REVERSAL_DAYS, placebo=True)
    print(f"  placebo, forecast under {PLACEBO_BELOW} days ({len(plc)} stock-quarters): "
          + "; ".join(f"{leg} right sign {sum(t[leg] > 0 for t in plc)}/{len(plc)}, average {statistics.mean(t[leg] for t in plc):+.2%}"
                      for leg in ("runup", "reversal")))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
