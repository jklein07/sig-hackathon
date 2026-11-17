"""Held-out run of strategy variant 5 (distance-method pairs), with the frozen code unchanged.

Usage (from scripts/):
  python -I pairs_distance_heldout.py design  <prices.csv> <output_dir>   reproduce the design result (wrapper check)
  python -I pairs_distance_heldout.py heldout <prices.csv> <output_dir>   the single held-out run

Every strategy function (select, run_portfolio, backtest, metrics, verdict, line) and every constant is imported
from the frozen scripts/pairs_distance.py. This file only chooses which rows are loaded and writes the report:
  - held-out: the last FORM (252) trading days of the design period, used only as the first portfolio's formation
    window, followed by every held-out day. Portfolios start on the first held-out day and every 21 trading days
    after it, as long as the full 126-day trading period ends by 2026-10-30. This is the design rule
    ("from the first day with 252 days of history") applied to the held-out period.
  - success bar: Sharpe >= 0.5 and at least 11 of 18 portfolios positive and >= 10 trades, as frozen. If the
    held-out period holds a different number of portfolios N, the portfolio count needed is ceil(11 / 18 x N).
The held-out run refuses to start unless pairs_distance.py, hypothesis-distance.md and this file match their
frozen fingerprints.
"""
import datetime as dt
import hashlib
import math
import os
import random
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)                    # -I drops the script folder
import pairs_distance as pdm                # frozen; nothing in it is changed or overridden

WINDOWS = {"design": (dt.date(2021, 11, 1), dt.date(2024, 10, 31)),
           "heldout": (dt.date(2024, 11, 1), dt.date(2026, 10, 30))}
FROZEN = ("hypothesis-distance.md", "scripts/pairs_distance.py", "scripts/pairs_distance_heldout.py")


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
    df = pd.read_csv(path, encoding="utf-8-sig")
    df["Date"] = pd.to_datetime(df["Date"], format="%m/%d/%Y").dt.date
    df = df.set_index("Date")
    before = df[df.index < start].tail(pdm.FORM)        # formation history only
    inside = df[(df.index >= start) & (df.index <= end)]
    out = pd.concat([before, inside])
    assert out.index[-1] <= end and out.notna().all().all()
    return out


def portfolios_needed(n_ports):
    return pdm.PORT_POS_MIN if n_ports == 18 else math.ceil(pdm.PORT_POS_MIN / 18 * n_ports)


def run(which, prices_path, out_dir):
    if which == "heldout":
        check_fingerprints()
    start, end = WINDOWS[which]
    px = load_window(prices_path, start, end)
    res = pdm.backtest(px)
    m = pdm.metrics(res)
    t = res["trades"]
    need = portfolios_needed(m["n_ports"])
    ok_trades = m["trades"] >= pdm.TRADES_MIN
    verdict = ("TOO FEW TO JUDGE" if not ok_trades else
               "SUPPORTED" if m["sharpe"] >= pdm.SHARPE_MIN and m["ports_pos"] >= need else "NOT SUPPORTED")
    label = "HELD-OUT PERIOD (single run)" if which == "heldout" else "DESIGN PERIOD (wrapper check; must match attempt #20)"
    L = [f"DISTANCE-METHOD PAIRS, {label}; frozen code from pairs_distance.py",
         f"Prices loaded {px.index[0]} to {px.index[-1]}; trading from {res['days'][res['first']]}; "
         f"{m['n_ports']} overlapping 6-month portfolios. After costs (5 bp per transaction, 0.5%/yr borrow).",
         "", "PORTFOLIOS (closest 3 of 7 same-business pairs at each formation)",
         res["ports"].to_string(index=False, float_format=lambda v: f"{v:+.2%}"), "", "TRADES"]
    if len(t):
        L.append(t[["pair", "portfolio_start", "signal_day", "fill_day", "exit_day", "reason", "gap_entry_sigmas",
                    "hold", "net_return_on_gross"]].to_string(index=False, float_format=lambda v: f"{v:+.4f}"))
    L += ["", "RESULT",
          f"  Annualised Sharpe {m['sharpe']:+.2f} (need >= {pdm.SHARPE_MIN}); portfolios positive {m['ports_pos']} of "
          f"{m['n_ports']} (need >= {need}); completed trades {m['trades']} (need >= {pdm.TRADES_MIN})",
          f"  Total return {m['total']:+.2%}; annualised volatility {m['vol']:.2%}; max drawdown {m['maxdd']:.2%}; "
          f"win rate {m['win']:.0%}; average hold {m['hold']:.1f} days; largest held exposure in a portfolio "
          f"{m['max_gross']:.0%} of its capital (at most 100% at entry)",
          "  Exits: " + (", ".join(f"{k} {v}" for k, v in t["reason"].value_counts().items()) if len(t) else "none"),
          f"  FROZEN TEST: {verdict}", "", "DECLARED CHECKS (not results)"]
    for name, kw in [("trigger 1.5 sigma", dict(trigger=1.5)), ("trigger 2.5 sigma", dict(trigger=2.5)),
                     ("cost 10 bp", dict(cost_bps=10)), ("cost 20 bp", dict(cost_bps=20)),
                     ("fixed three pairs", dict(fixed=pdm.FIXED3)), ("all 7 candidates", dict(k=7)),
                     ("same-day fills", dict(same_day=True))]:
        L.append(f"  {name}: {pdm.line(pdm.metrics(pdm.backtest(px, **kw)))}")
    if len(t):
        L.append("  by pair: " + "; ".join(f"{p} {len(g)} trades, win {(g['pnl'] > 0).mean():.0%}, "
                                           f"average {g['net_return_on_gross'].mean():+.2%} on gross"
                                           for p, g in t.groupby("pair")))
    rng = random.Random(pdm.SEED)
    sh = []
    for _ in range(pdm.PLACEBO_DRAWS):
        tk = rng.sample(pdm.OIL, 6)
        sh.append(pdm.metrics(pdm.backtest(px, fixed=[(tk[0], tk[1]), (tk[2], tk[3]), (tk[4], tk[5])]))["sharpe"])
    L.append(f"  placebo, {pdm.PLACEBO_DRAWS} draws of three random oil pairs: median Sharpe {np.median(sh):+.2f}; "
             f"share at least as good as the main result {np.mean([x >= m['sharpe'] for x in sh]):.0%}")
    text = "\n".join(L)
    print(text)
    tag = "heldout" if which == "heldout" else "design_wrappercheck"
    with open(os.path.join(out_dir, f"distance_backtest_{tag}.txt"), "w") as f:
        f.write(text + "\n")
    if which == "heldout":
        t.to_csv(os.path.join(out_dir, "distance_trades_heldout.csv"), index=False)
        res["ports"].to_csv(os.path.join(out_dir, "distance_portfolios_heldout.csv"), index=False)
        eq = np.cumprod(1 + res["R"][res["first"]:])
        pd.DataFrame({"date": res["days"][res["first"]:], "daily_return": res["R"][res["first"]:], "equity": eq}).to_csv(
            os.path.join(out_dir, "distance_equity_heldout.csv"), index=False)
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(9, 3.6))
        ax.plot(pd.to_datetime(res["days"][res["first"]:]), eq, color="#1f5f99", lw=1.6)
        ax.axhline(1, color="#888", lw=0.8)
        ax.set_title("Distance-method pairs, growth of $1, held-out period (after costs)", fontsize=10)
        ax.spines[["top", "right"]].set_visible(False)
        fig.tight_layout()
        fig.savefig(os.path.join(out_dir, "distance_equity_heldout.png"), dpi=160)
        plt.close(fig)


if __name__ == "__main__":
    run(sys.argv[1], sys.argv[2], sys.argv[3])
