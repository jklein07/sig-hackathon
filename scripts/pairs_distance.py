"""Strategy variant 5: distance-method pairs (Gatev, Goetzmann and Rouwenhorst 2006) within the same business.
Rules in hypothesis-distance.md.

Usage: python -I pairs_distance.py <prices.csv> <output_dir>     design-period back-test and declared checks
       python -I pairs_distance.py --selftest                     synthetic prices only

Rows after DESIGN_END are never used. Every number that defines the strategy is a constant below.
"""
import datetime as dt
import math
import os
import random
import sys

import numpy as np
import pandas as pd

DESIGN_END = dt.date(2024, 10, 31)
CANDIDATES = [("XOM", "CVX"), ("COP", "EOG"), ("COP", "OXY"), ("EOG", "OXY"), ("MPC", "VLO"), ("MPC", "PSX"), ("PSX", "VLO")]
FIXED3 = [("XOM", "CVX"), ("COP", "EOG"), ("MPC", "VLO")]
OIL = ["XOM", "CVX", "COP", "EOG", "OXY", "SLB", "MPC", "PSX", "VLO", "XLE", "XOP", "OIH"]

FORM, TRADE, STEP = 252, 126, 21
SLEEVES = TRADE // STEP          # 6 live portfolios at most
TOP_K, TRIGGER = 3, 2.0
COST_BPS, BORROW = 5, 0.005
SHARPE_MIN, PORT_POS_MIN, TRADES_MIN = 0.5, 11, 10
PLACEBO_DRAWS, SEED = 200, 20261113


def load_prices(path):
    df = pd.read_csv(path, encoding="utf-8-sig")
    df["Date"] = pd.to_datetime(df["Date"], format="%m/%d/%Y").dt.date
    df = df[df["Date"] <= DESIGN_END].set_index("Date")
    assert df.index[-1] <= DESIGN_END and df.notna().all().all()
    return df


def select(px, s, cands, k):
    """Closest k pairs over the formation window [s-FORM, s-1], with each pair's gap sigma."""
    out = []
    for A, B in cands:
        a = px[A].to_numpy()[s - FORM:s]
        b = px[B].to_numpy()[s - FORM:s]
        g = a / a[0] - b / b[0]
        out.append({"pair": (A, B), "dist": float((g ** 2).sum()), "sigma": float(g.std(ddof=1))})
    out.sort(key=lambda x: x["dist"])
    return out[:k]


def run_portfolio(px, s, chosen, trigger, cost, same_day):
    """One portfolio's trading period [s, s+TRADE). Returns daily returns on its own capital and its trades."""
    days = px.index
    e = s + TRADE
    cap = 1.0
    r = np.zeros(TRADE)
    trades = []
    state = {c["pair"]: {"open": None, "pend": None} for c in chosen}
    alloc = 1.0 / len(chosen)
    max_gross = [0.0]                     # largest held exposure / portfolio capital (legs drift; entry is capped)
    for t in range(s, e):
        pnl = 0.0
        for c in chosen:
            A, B = c["pair"]
            st = state[c["pair"]]
            tr = st["open"]
            if tr is not None and t > tr["fill_i"]:
                rA = px[A].iat[t] / px[A].iat[t - 1] - 1
                rB = px[B].iat[t] / px[B].iat[t - 1] - 1
                d = tr["legA"] * rA + tr["legB"] * rB
                tr["legA"] *= 1 + rA
                tr["legB"] *= 1 + rB
                d -= (-min(tr["legA"], 0) - min(tr["legB"], 0)) * BORROW / 252
                tr["pnl"] += d
                pnl += d
            g = px[A].iat[t] / px[A].iat[s - 1] - px[B].iat[t] / px[B].iat[s - 1]
            # fills scheduled yesterday (or today, if same_day)
            if st["pend"] == "close" or (tr is not None and t == e - 1):
                c_ = cost * (abs(tr["legA"]) + abs(tr["legB"]))
                tr["pnl"] -= c_
                pnl -= c_
                tr.update(exit_day=days[t], hold=t - tr["fill_i"],
                          reason="prices crossed" if st["pend"] == "close" else "period end")
                trades.append(tr)
                st["open"], st["pend"], tr = None, None, None
            elif isinstance(st["pend"], dict):
                sig = st["pend"]
                gross = alloc * cap
                d_ = -1.0 if sig["g"] > 0 else 1.0               # +1 = long A
                tr = {"pair": f"{A}-{B}", "portfolio_start": days[s], "signal_day": sig["day"], "fill_day": days[t],
                      "fill_i": t, "gap_entry_sigmas": round(sig["g"] / c["sigma"], 2), "dir": d_,
                      "legA": d_ * gross / 2, "legB": -d_ * gross / 2, "gross0": gross, "pnl": 0.0}
                assert gross <= alloc * cap * (1 + 1e-9)   # no leverage at entry
                c_ = cost * gross
                tr["pnl"] -= c_
                pnl -= c_
                st["open"], st["pend"] = tr, None
            # signals at today's close
            act_today = same_day and t < e - 1
            if tr is not None:
                if g * (-tr["dir"]) <= 0 and t < e - 1 and st["pend"] is None:
                    st["pend"] = "close"
                    if act_today:
                        c_ = cost * (abs(tr["legA"]) + abs(tr["legB"]))
                        tr["pnl"] -= c_
                        pnl -= c_
                        tr.update(exit_day=days[t], hold=t - tr["fill_i"], reason="prices crossed")
                        trades.append(tr)
                        st["open"], st["pend"] = None, None
            elif st["pend"] is None and abs(g) > trigger * c["sigma"] and t + 1 < e - 1:
                st["pend"] = {"g": g, "day": days[t]}
                if act_today and t < e - 2:
                    st["pend"] = None
                    gross = alloc * cap
                    d_ = -1.0 if g > 0 else 1.0
                    st["open"] = {"pair": f"{A}-{B}", "portfolio_start": days[s], "signal_day": days[t], "fill_day": days[t],
                                  "fill_i": t, "gap_entry_sigmas": round(g / c["sigma"], 2), "dir": d_,
                                  "legA": d_ * gross / 2, "legB": -d_ * gross / 2, "gross0": gross, "pnl": -cost * gross}
                    pnl -= cost * gross
        gross_now = sum(abs(st["open"]["legA"]) + abs(st["open"]["legB"]) for st in state.values() if st["open"])
        max_gross[0] = max(max_gross[0], gross_now / (cap + pnl))
        r[t - s] = pnl / cap
        cap += pnl
    return r, trades, max_gross[0]


def backtest(px, cands=CANDIDATES, k=TOP_K, trigger=TRIGGER, cost_bps=COST_BPS, fixed=None, same_day=False):
    n = len(px)
    starts = list(range(FORM, n - TRADE + 1, STEP))
    R = np.zeros(n)
    trades, ports = [], []
    for s in starts:
        chosen = select(px, s, fixed if fixed else cands, len(fixed) if fixed else k)
        r, tr, mg = run_portfolio(px, s, chosen, trigger, cost_bps / 1e4, same_day)
        R[s:s + TRADE] += r / SLEEVES
        trades += tr
        ports.append({"start": px.index[s], "end": px.index[s + TRADE - 1],
                      "pairs": ", ".join(f"{c['pair'][0]}-{c['pair'][1]}" for c in chosen),
                      "return": float(np.prod(1 + r) - 1), "trades": len(tr), "max_held_gross": mg})
    t = pd.DataFrame([{kk: v for kk, v in x.items() if kk not in ("fill_i", "legA", "legB")}
                      | {"net_return_on_gross": x["pnl"] / x["gross0"]} for x in trades])
    return {"R": R, "first": starts[0], "days": list(px.index), "trades": t, "ports": pd.DataFrame(ports)}


def metrics(res):
    r = res["R"][res["first"]:]
    eq = np.cumprod(1 + r)
    sd = r.std(ddof=1)
    t = res["trades"]
    n_tr = len(t)
    return {"sharpe": r.mean() / sd * math.sqrt(252) if sd > 0 else 0.0, "total": float(eq[-1] - 1),
            "maxdd": float((eq / np.maximum.accumulate(eq) - 1).min()), "vol": float(sd * math.sqrt(252)),
            "ports_pos": int((res["ports"]["return"] > 0).sum()), "max_gross": float(res["ports"]["max_held_gross"].max()), "n_ports": len(res["ports"]), "trades": n_tr,
            "win": float((t["pnl"] > 0).mean()) if n_tr else float("nan"),
            "hold": float(t["hold"].mean()) if n_tr else float("nan")}


def verdict(m):
    if m["trades"] < TRADES_MIN:
        return "TOO FEW TO JUDGE"
    return "SUPPORTED" if m["sharpe"] >= SHARPE_MIN and m["ports_pos"] >= PORT_POS_MIN else "NOT SUPPORTED"


def line(m):
    return (f"Sharpe {m['sharpe']:+.2f}, total {m['total']:+.2%}, max drawdown {m['maxdd']:.2%}, "
            f"portfolios positive {m['ports_pos']}/{m['n_ports']}, trades {m['trades']}")


def run(prices_path, out):
    px = load_prices(prices_path)
    res = backtest(px)
    m = metrics(res)
    t = res["trades"]
    L = [f"DISTANCE-METHOD PAIRS, DESIGN PERIOD ONLY (prices {px.index[0]} to {px.index[-1]}); rules as frozen in hypothesis-distance.md",
         f"Trading from {res['days'][res['first']]}; {m['n_ports']} overlapping 6-month portfolios. After costs (5 bp per transaction, 0.5%/yr borrow).",
         "", "PORTFOLIOS (closest 3 of 7 same-business pairs at each formation)"]
    L.append(res["ports"].to_string(index=False, float_format=lambda v: f"{v:+.2%}"))
    L += ["", "TRADES"]
    if len(t):
        L.append(t[["pair", "portfolio_start", "signal_day", "fill_day", "exit_day", "reason", "gap_entry_sigmas",
                    "hold", "net_return_on_gross"]].to_string(index=False, float_format=lambda v: f"{v:+.4f}"))
    L += ["", "RESULT",
          f"  Annualised Sharpe {m['sharpe']:+.2f} (need >= {SHARPE_MIN}); portfolios positive {m['ports_pos']} of {m['n_ports']} "
          f"(need >= {PORT_POS_MIN}); completed trades {m['trades']} (need >= {TRADES_MIN})",
          f"  Total return {m['total']:+.2%}; annualised volatility {m['vol']:.2%}; max drawdown {m['maxdd']:.2%}; "
          f"win rate {m['win']:.0%}; average hold {m['hold']:.1f} days; largest held exposure in a portfolio "
          f"{m['max_gross']:.0%} of its capital (at most 100% at entry)",
          f"  Exits: " + (", ".join(f"{k_} {v}" for k_, v in t["reason"].value_counts().items()) if len(t) else "none"),
          f"  FROZEN TEST: {verdict(m)}", "", "DECLARED CHECKS (not results)"]
    for name, kw in [("trigger 1.5 sigma", dict(trigger=1.5)), ("trigger 2.5 sigma", dict(trigger=2.5)),
                     ("cost 10 bp", dict(cost_bps=10)), ("cost 20 bp", dict(cost_bps=20)),
                     ("fixed three pairs", dict(fixed=FIXED3)), ("all 7 candidates", dict(k=7)),
                     ("same-day fills", dict(same_day=True))]:
        L.append(f"  {name}: {line(metrics(backtest(px, **kw)))}")
    if len(t):
        L.append("  by pair: " + "; ".join(f"{p} {len(g)} trades, win {(g['pnl'] > 0).mean():.0%}, "
                                           f"average {g['net_return_on_gross'].mean():+.2%} on gross"
                                           for p, g in t.groupby("pair")))
    rng = random.Random(SEED)
    sh = []
    for _ in range(PLACEBO_DRAWS):
        tk = rng.sample(OIL, 6)
        sh.append(metrics(backtest(px, fixed=[(tk[0], tk[1]), (tk[2], tk[3]), (tk[4], tk[5])]))["sharpe"])
    L.append(f"  placebo, {PLACEBO_DRAWS} draws of three random oil pairs: median Sharpe {np.median(sh):+.2f}; "
             f"share at least as good as the main result {np.mean([x >= m['sharpe'] for x in sh]):.0%}")
    text = "\n".join(L)
    print(text)
    with open(os.path.join(out, "distance_backtest_design.txt"), "w") as f:
        f.write(text + "\n")
    t.to_csv(os.path.join(out, "distance_trades_design.csv"), index=False)
    res["ports"].to_csv(os.path.join(out, "distance_portfolios_design.csv"), index=False)
    pd.DataFrame({"date": res["days"][res["first"]:], "daily_return": res["R"][res["first"]:],
                  "equity": np.cumprod(1 + res["R"][res["first"]:])}).to_csv(os.path.join(out, "distance_equity_design.csv"), index=False)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    d = pd.to_datetime(res["days"][res["first"]:])
    fig, ax = plt.subplots(figsize=(9, 3.6))
    ax.plot(d, np.cumprod(1 + res["R"][res["first"]:]), color="#1f5f99", lw=1.6)
    ax.axhline(1, color="#888", lw=0.8)
    ax.set_title("Distance-method pairs, growth of $1, design period (after costs)", fontsize=10)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(os.path.join(out, "distance_equity_design.png"), dpi=160)
    plt.close(fig)


def selftest():
    rng = np.random.default_rng(3)
    n = 755
    days = pd.bdate_range("2021-11-01", periods=n).date
    common = np.cumsum(rng.normal(0, 0.012, n))
    u = np.zeros(n)
    for i in range(1, n):
        u[i] = 0.9 * u[i - 1] + rng.normal(0, 0.01)
    cols = {"A": np.exp(4 + common + u), "B": np.exp(4 + common)}
    for c in ("C", "D", "E", "F"):
        cols[c] = np.exp(4 + np.cumsum(rng.normal(0, 0.015, n)))
    px = pd.DataFrame(cols, index=days)
    cands = [("A", "B"), ("C", "D"), ("E", "F"), ("A", "C")]
    res = backtest(px, cands=cands, k=1)
    m = metrics(res)
    picked = (res["ports"]["pairs"] == "A-B").mean()
    print(f"planted pair chosen in {picked:.0%} of portfolios; {m['trades']} trades; Sharpe {m['sharpe']:+.2f}; "
          f"win rate {m['win']:.0%}")
    assert picked >= 0.8, "planted pair not picked by distance"
    assert m["trades"] >= 10 and m["sharpe"] > 0, "planted pair not traded profitably"
    rs = backtest(px, cands=cands, k=1, same_day=True)
    assert len(rs["trades"]) >= 10
    t = res["trades"]
    assert ((t["exit_day"] > t["fill_day"]) | (t["reason"] == "period end")).all()
    print("SELFTEST PASSED")


if __name__ == "__main__":
    if sys.argv[1:] == ["--selftest"]:
        selftest()
    else:
        run(sys.argv[1], sys.argv[2])
