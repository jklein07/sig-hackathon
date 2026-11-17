"""Diagnostic for strategy variant 1 (XLE rebalance): where the run-up and reversal returns come from.

Usage: python -I diag_flow_legs.py <prices.csv> <forecast_signals.csv>

Design period only (reuses backtest_design.py's loader and DESIGN_END guard). Not a new strategy:
the frozen rules and verdict in hypothesis.md are unchanged. This breaks the two legs down by
fund direction, by stock vs XLE, by rebalance, and day by day around the rebalance.
"""
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # -I drops the script folder

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import backtest_design as bd

COST_LEG = 4 * bd.COST_BPS / 1e4
PRE, POST = 5, 10            # days shown before the entry day and after the rebalance in the event path


def ret(px, t, i0, i1):
    return px[t][i1] / px[t][i0] - 1


def legs_detail(trades, px):
    for t in trades:
        s, d = t["ticker"], t["dir"]
        t["runup_stock"] = d * ret(px, s, t["entry"], t["reb"])
        t["runup_xle"] = -d * ret(px, bd.HEDGE, t["entry"], t["reb"])
        t["rev_stock"] = -d * ret(px, s, t["reb"], t["exit"])
        t["rev_xle"] = d * ret(px, bd.HEDGE, t["reb"], t["exit"])
        t["both"] = t["runup"] + t["reversal"]          # run-up, then flip at the rebalance close
    return trades


def line(name, xs, cost=COST_LEG):
    if not xs:
        return f"  {name:<34} none"
    return (f"  {name:<34} n={len(xs):>2}  right {sum(x > 0 for x in xs):>2}/{len(xs):<2}  "
            f"avg {statistics.mean(xs):+.2%}  after cost {statistics.mean(xs) - cost:+.2%}  "
            f"sum after cost {sum(x - cost for x in xs):+.2%}")


def report(label, trades):
    print(f"\n=== {label} ({len(trades)} signals) ===")
    for leg, key in (("RUN-UP", "runup"), ("REVERSAL", "reversal")):
        print(f"{leg}")
        print(line("all", [t[key] for t in trades]))
        print(line("fund buys (long stock)", [t[key] for t in trades if t["dir"] > 0]))
        print(line("fund sells (short stock)", [t[key] for t in trades if t["dir"] < 0]))
        best = max(trades, key=lambda t: t[key])
        print(line(f"without best ({best['ticker']} {best['rebalance']})", [t[key] for t in trades if t is not best]))
        pre = "runup" if key == "runup" else "rev"
        print(f"  {'split, before cost':<34} stock side {statistics.mean(t[pre + '_stock'] for t in trades):+.2%}, "
              f"XLE hedge side {statistics.mean(t[pre + '_xle'] for t in trades):+.2%} (sum = avg above)")
        by = {}
        for t in trades:
            by.setdefault(t["rebalance"], []).append(t[key])
        print("  by rebalance (avg before cost): " + ", ".join(f"{e} {statistics.mean(v):+.2%} (n={len(v)})"
                                                              for e, v in sorted(by.items())))
    print("BOTH LEGS BACK TO BACK (2 legs of cost)")
    print(line("all", [t["both"] for t in trades], 2 * COST_LEG))
    print("RUN-UP vs REVERSAL on the same signal: "
          f"both right {sum(t['runup'] > 0 and t['reversal'] > 0 for t in trades)}, "
          f"run-up only {sum(t['runup'] > 0 >= t['reversal'] for t in trades)}, "
          f"reversal only {sum(t['reversal'] > 0 >= t['runup'] for t in trades)}, "
          f"neither {sum(t['runup'] <= 0 and t['reversal'] <= 0 for t in trades)}")


def event_path(trades, px, n_days):
    """Average signed (fund direction) stock-minus-XLE return, cumulated from PRE days before entry."""
    offsets, paths = None, []
    for t in trades:
        start = t["entry"] - PRE
        end = t["reb"] + POST
        if start < 0 or end >= n_days:
            continue
        # x axis: days relative to the rebalance close; entry sits at entry - reb
        rel = list(range(start - t["reb"], end - t["reb"] + 1))
        vals = [t["dir"] * bd.spread(px, t["ticker"], start, start + k) for k in range(end - start + 1)]
        paths.append(dict(zip(rel, vals)))
    common = sorted(set.intersection(*(set(p) for p in paths)))
    avg = [statistics.mean(p[k] - p[0] for p in paths) for k in common]   # re-based to 0 at the rebalance close
    return common, avg, len(paths)


def main(prices_path, signals_path):
    days, px = bd.load_prices(prices_path)
    import csv, datetime as dt
    with open(signals_path, newline="") as f:
        signals = [{"snapshot": dt.date.fromisoformat(r["snapshot_day"]), "rebalance": dt.date.fromisoformat(r["rebalance_day"]),
                    "ticker": r["ticker"], "forecast": float(r["forecast_days"])} for r in csv.DictReader(f)]
    print(f"DIAGNOSTIC, DESIGN PERIOD ONLY ({days[0]} to {days[-1]}). Strategy variant 1, frozen rules unchanged.")
    print("Returns signed so positive = prediction right; cost per leg 0.20% (4 x 5 bp).")

    main_tr = legs_detail(bd.build(signals, days, px, bd.THRESHOLD_DAYS, bd.REVERSAL_DAYS), px)
    wide_tr = legs_detail(bd.build(signals, days, px, 0.25, bd.REVERSAL_DAYS), px)
    plc_tr = legs_detail(bd.build(signals, days, px, bd.THRESHOLD_DAYS, bd.REVERSAL_DAYS, placebo=True), px)
    report("MAIN RULE: forecast >= 0.5 days", main_tr)
    report("CHECK: forecast >= 0.25 days", wide_tr)
    report("PLACEBO: forecast < 0.25 days", plc_tr)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    for tr, lab, c in ((main_tr, "forecast >= 0.5 days", "#1f5fa8"), (wide_tr, "forecast >= 0.25 days", "#7aa6d8"),
                       (plc_tr, "placebo < 0.25 days", "#999999")):
        x, y, n = event_path(tr, px, len(days))
        ax.plot(x, [v * 100 for v in y], label=f"{lab} (n={n})", color=c, lw=2 if c == "#1f5fa8" else 1.3)
    ax.axvline(0, color="k", lw=0.8)
    ax.axhline(0, color="k", lw=0.5, ls=":")
    ax.set_xlabel("trading days relative to the rebalance close (0)")
    ax.set_ylabel("stock minus XLE, % (in the fund's direction)\nre-based to 0 at the rebalance close")
    ax.set_title("XLE rebalance: average move in the fund's direction, design period")
    ax.text(0.01, 0.02, "Rising before 0 = run-up pays; falling after 0 = reversal pays", transform=ax.transAxes, fontsize=8)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig("../output/diag_flow_event_path.png", dpi=150)
    print("\nChart: output/diag_flow_event_path.png")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
