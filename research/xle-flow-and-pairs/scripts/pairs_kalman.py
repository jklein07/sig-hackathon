"""Strategy variant 3: Kalman-filter pairs on three same-business pairs (rules in hypothesis-pairs.md).

Usage: python -I pairs_kalman.py <prices.csv> <output_dir>     design-period back-test, all declared checks
       python -I pairs_kalman.py --selftest                     synthetic prices only

Rows after DESIGN_END are never used. Every number that defines the strategy is a constant below and
matches hypothesis-pairs.md; the declared checks change one thing at a time.
"""
import datetime as dt
import math
import os
import random
import sys

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.stattools import coint

DESIGN_END = dt.date(2024, 10, 31)
PAIRS = [("XOM", "CVX"), ("COP", "EOG"), ("MPC", "VLO")]
EXTRA_PAIRS = [("COP", "OXY"), ("EOG", "OXY"), ("MPC", "PSX"), ("PSX", "VLO"), ("SLB", "OIH"), ("COP", "XOP")]
OIL = ["XOM", "CVX", "COP", "EOG", "OXY", "SLB", "MPC", "PSX", "VLO", "XLE", "XOP", "OIH"]
VIX = "VIX (index, not tradable)"

FORM, BLOCK = 252, 63
P_MAX, HL_MIN, HL_MAX = 0.05, 5, 63
Q_DIV = 252                  # daily state noise = formation OLS coefficient covariance / Q_DIV
ENTRY, STOP = 2.0, 4.0
TIME_STOP_HL = 2
VIX_PCT, VIX_LOOKBACK = 80, 252
COST_BPS, BORROW = 5, 0.005
SHARPE_MIN, BLOCKS_POS_MIN, TRADES_MIN = 0.5, 5, 10
PLACEBO_DRAWS, SEED = 200, 20261113


# ---------------------------------------------------------------- data
def load_prices(path):
    df = pd.read_csv(path, encoding="utf-8-sig")
    df["Date"] = pd.to_datetime(df["Date"], format="%m/%d/%Y").dt.date
    df = df[df["Date"] <= DESIGN_END].set_index("Date")
    assert df.index[-1] <= DESIGN_END and df.notna().all().all()
    return df


# ---------------------------------------------------------------- formation
def formation(la, lb):
    X = sm.add_constant(lb)
    ols = sm.OLS(la, X).fit()
    a, b = ols.params
    resid = la - a - b * lb
    p = coint(la, lb)[1]
    ds = np.diff(resid)
    slope = sm.OLS(ds, sm.add_constant(resid[:-1])).fit().params[1]
    hl = -math.log(2) / math.log(1 + slope) if -1 < slope < 0 else math.inf
    return {"a": a, "b": b, "cov": np.asarray(ols.cov_params()), "R": float(np.var(resid, ddof=2)),
            "mean": float(resid.mean()), "sd": float(resid.std(ddof=1)), "p": float(p), "hl": hl,
            "eligible": bool(p < P_MAX and HL_MIN <= hl <= HL_MAX)}


def signal_path(la, lb, f, hedge, qdiv):
    """z each day of the block, plus the frozen-hedge tuple (alpha, beta, offset, scale) that produced it."""
    n = len(la)
    z = np.empty(n)
    frozen = []
    if hedge == "ols":
        for t in range(n):
            z[t] = (la[t] - f["a"] - f["b"] * lb[t] - f["mean"]) / f["sd"]
            frozen.append((f["a"], f["b"], f["mean"], f["sd"]))
        return z, frozen
    x = np.array([f["a"], f["b"]], dtype=float)
    P = f["cov"].copy()
    Q = f["cov"] / qdiv
    for t in range(n):
        P = P + Q
        H = np.array([1.0, lb[t]])
        e = la[t] - H @ x
        S = float(H @ P @ H + f["R"])
        z[t] = e / math.sqrt(S)
        frozen.append((x[0], x[1], 0.0, math.sqrt(S)))
        K = P @ H / S
        x = x + K * e
        P = P - np.outer(K, H) @ P
    return z, frozen


# ---------------------------------------------------------------- back-test
def backtest(px, pairs, hedge="kalman", qdiv=Q_DIV, entry=ENTRY, vix_on=True, cost_bps=COST_BPS):
    n = len(px)
    days = list(px.index)
    lp = np.log(px)
    vix = px[VIX].to_numpy() if VIX in px else np.zeros(n)
    blocks = [(s, min(s + BLOCK, n)) for s in range(FORM, n, BLOCK)]
    cost = cost_bps / 1e4
    r = np.zeros(n)
    inmkt = np.zeros(n, dtype=bool)
    gross_used = np.zeros(n)
    equity = 1.0
    trades, elig = [], []
    zplot = {p: np.full(n, np.nan) for p in pairs}

    for bi, (s, e) in enumerate(blocks):
        forms = {}
        for (A, B) in pairs:
            f = formation(lp[A].to_numpy()[s - FORM:s], lp[B].to_numpy()[s - FORM:s])
            forms[(A, B)] = f
            elig.append({"block": bi + 1, "start": days[s], "end": days[e - 1], "pair": f"{A}-{B}",
                         "coint_p": round(f["p"], 4), "half_life": round(f["hl"], 1), "beta_ols": round(f["b"], 3),
                         "eligible": f["eligible"]})
        live = [p for p in pairs if forms[p]["eligible"]]
        N = len(live)
        paths = {}
        for p in live:
            A, B = p
            z, fr = signal_path(lp[A].to_numpy()[s:e], lp[B].to_numpy()[s:e], forms[p], hedge, qdiv)
            paths[p] = (z, fr)
            zplot[p][s:e] = z
        open_tr, pend_in, pend_out = {}, {}, {}

        for t in range(s, e):
            k = t - s
            pnl = 0.0
            # 1) mark open positions from yesterday's close to today's
            for p, tr in open_tr.items():
                A, B = p
                rA, rB = px[A].iat[t] / px[A].iat[t - 1] - 1, px[B].iat[t] / px[B].iat[t - 1] - 1
                d = tr["legA"] * rA + tr["legB"] * rB
                tr["legA"] *= 1 + rA
                tr["legB"] *= 1 + rB
                short_val = -min(tr["legA"], 0) - min(tr["legB"], 0)
                d -= short_val * BORROW / 252
                tr["pnl"] += d
                pnl += d
            # 2) exits filled at today's close (scheduled yesterday, or block end)
            for p in list(open_tr):
                if p in pend_out or t == e - 1:
                    tr = open_tr.pop(p)
                    c = cost * (abs(tr["legA"]) + abs(tr["legB"]))
                    tr["pnl"] -= c
                    pnl -= c
                    tr.update(exit_day=days[t], reason=pend_out.pop(p, "block end"), hold=t - tr["fill_i"])
                    trades.append(tr)
            # 3) entries filled at today's close (scheduled yesterday)
            for p, sig in list(pend_in.items()):
                del pend_in[p]
                A, B = p
                al, be, off, sc = sig["frozen"]
                G = equity / N
                d = -1.0 if sig["z"] > 0 else 1.0          # +1 = long A
                legA = d * G / (1 + abs(be))
                legB = -d * math.copysign(1.0, be) * G * abs(be) / (1 + abs(be))
                c = cost * (abs(legA) + abs(legB))
                pnl -= c
                open_tr[p] = {"pair": f"{A}-{B}", "block": bi + 1, "signal_day": sig["day"], "fill_day": days[t],
                              "fill_i": t, "z_entry": round(sig["z"], 2), "beta": round(be, 3), "dir": d,
                              "gross0": G, "legA": legA, "legB": legB, "pnl": -c, "frozen": sig["frozen"],
                              "hl": forms[p]["hl"], "filter_cross_i": None, "trade_cross_i": None}
                # no leverage at entry: each trade is 1/N of equity and at most N trades are open
                assert len(open_tr) <= N and abs(legA) + abs(legB) <= equity / N * (1 + 1e-9)
            # 4) signals at today's close, acted on at tomorrow's close
            for p in live:
                A, B = p
                z, fr = paths[p]
                if p in open_tr:
                    tr = open_tr[p]
                    if t > tr["fill_i"] - 1:
                        al, be, off, sc = tr["frozen"]
                        zt = (lp[A].iat[t] - al - be * lp[B].iat[t] - off) / sc
                        sgn0 = -tr["dir"]                      # sign of z at entry
                        if tr["filter_cross_i"] is None and z[k] * sgn0 <= 0:
                            tr["filter_cross_i"] = t
                        reason = None
                        if zt * sgn0 <= 0:
                            reason = "crossed zero"
                            tr["trade_cross_i"] = t
                        elif abs(zt) >= STOP:
                            reason = "stop-loss"
                        elif t - tr["fill_i"] >= math.ceil(TIME_STOP_HL * tr["hl"]):
                            reason = "time stop"
                        if reason and t < e - 1:
                            pend_out[p] = reason
                    continue
                if p in pend_in or k == 0 or t + 1 >= e - 1:
                    continue
                if abs(z[k]) >= entry and abs(z[k - 1]) < entry:
                    if vix_on and t >= VIX_LOOKBACK and vix[t] > np.percentile(vix[t - VIX_LOOKBACK:t], VIX_PCT):
                        continue
                    pend_in[p] = {"z": float(z[k]), "frozen": fr[k], "day": days[t]}
            inmkt[t] = bool(open_tr)
            gross_used[t] = sum(abs(tr["legA"]) + abs(tr["legB"]) for tr in open_tr.values()) / (equity + pnl)
            r[t] = pnl / equity
            equity += pnl

    tdf = pd.DataFrame([{k: v for k, v in tr.items() if k not in ("frozen", "fill_i", "legA", "legB", "hl")}
                        | {"net_return_on_gross": tr["pnl"] / tr["gross0"], "net_pnl_pct_equity": tr["pnl"],
                           "filter_crossed_first": (tr["filter_cross_i"] is not None and
                                                    (tr["trade_cross_i"] is None or tr["filter_cross_i"] < tr["trade_cross_i"]))}
                        for tr in trades])
    return {"days": days, "r": r, "blocks": blocks, "trades": tdf, "elig": pd.DataFrame(elig), "z": zplot,
            "inmkt": inmkt, "gross": gross_used}


def metrics(res):
    s0 = res["blocks"][0][0]
    r = res["r"][s0:]
    eq = np.cumprod(1 + r)
    sd = r.std(ddof=1)
    sharpe = r.mean() / sd * math.sqrt(252) if sd > 0 else 0.0
    block_ret = [float(np.prod(1 + res["r"][s:e]) - 1) for s, e in res["blocks"]]
    t = res["trades"]
    n_tr = len(t)
    return {"sharpe": sharpe, "total": float(eq[-1] - 1), "maxdd": float((eq / np.maximum.accumulate(eq) - 1).min()),
            "block_ret": block_ret, "blocks_pos": sum(x > 0 for x in block_ret), "trades": n_tr,
            "win": float((t["net_pnl_pct_equity"] > 0).mean()) if n_tr else float("nan"),
            "hold": float(t["hold"].mean()) if n_tr else float("nan"),
            "inmkt": float(res["inmkt"][s0:].mean()), "max_gross": float(res["gross"][s0:].max()),
            "ann_vol": float(sd * math.sqrt(252))}


def verdict(m):
    if m["trades"] < TRADES_MIN:
        return "TOO FEW TO JUDGE"
    ok = m["sharpe"] >= SHARPE_MIN and m["blocks_pos"] >= BLOCKS_POS_MIN
    return "SUPPORTED" if ok else "NOT SUPPORTED"


def line(m):
    return (f"Sharpe {m['sharpe']:+.2f}, total {m['total']:+.2%}, max drawdown {m['maxdd']:.2%}, "
            f"blocks positive {m['blocks_pos']}/8, trades {m['trades']}")


# ---------------------------------------------------------------- report
def run(prices_path, out):
    px = load_prices(prices_path)
    print(f"PAIRS (KALMAN), DESIGN PERIOD ONLY: prices {px.index[0]} to {px.index[-1]}; rules as frozen in hypothesis-pairs.md")
    res = backtest(px, PAIRS)
    m = metrics(res)
    L = [f"PAIRS (KALMAN) BACK-TEST, DESIGN PERIOD ONLY ({px.index[0]} to {px.index[-1]})",
         f"Trading blocks: {len(res['blocks'])}, {res['days'][res['blocks'][0][0]]} to {res['days'][-1]}. "
         "All figures after costs (5 bp per transaction, 0.5%/yr borrow).", "",
         "ELIGIBILITY (formation window: Engle-Granger p < 0.05 and half-life 5-63 days)"]
    L.append(res["elig"].to_string(index=False))
    L += ["", "BLOCKS"]
    for i, ((s, e), br) in enumerate(zip(res["blocks"], m["block_ret"])):
        el = res["elig"][(res["elig"]["block"] == i + 1) & res["elig"]["eligible"]]["pair"].tolist()
        L.append(f"  block {i + 1}  {res['days'][s]} to {res['days'][e - 1]}  return {br:+.2%}  eligible: {', '.join(el) or 'none'}")
    L += ["", "TRADES"]
    t = res["trades"]
    if len(t):
        cols = ["pair", "block", "signal_day", "fill_day", "exit_day", "reason", "z_entry", "beta", "hold",
                "net_return_on_gross", "net_pnl_pct_equity", "filter_crossed_first"]
        L.append(t[cols].to_string(index=False, float_format=lambda v: f"{v:+.4f}"))
    else:
        L.append("  none")
    L += ["", "RESULT",
          f"  Annualised Sharpe {m['sharpe']:+.2f} (need >= {SHARPE_MIN}); blocks positive {m['blocks_pos']} of 8 (need >= {BLOCKS_POS_MIN}); "
          f"completed trades {m['trades']} (need >= {TRADES_MIN})",
          f"  Total return {m['total']:+.2%}; annualised volatility {m['ann_vol']:.2%}; max drawdown {m['maxdd']:.2%}; "
          f"win rate {m['win']:.0%}; average hold {m['hold']:.1f} days; in the market {m['inmkt']:.0%} of days; "
          f"max gross exposure {m['max_gross']:.0%} of equity",
          f"  FROZEN TEST: {verdict(m)}"]

    L += ["", "DECLARED CHECKS (not results)"]
    checks = [("rolling-regression hedge", dict(hedge="ols")), ("state noise cov/1008 (slower hedge)", dict(qdiv=1008)),
              ("state noise cov/63 (faster hedge)", dict(qdiv=63)), ("entry 1.5", dict(entry=1.5)), ("entry 2.5", dict(entry=2.5)),
              ("no VIX filter", dict(vix_on=False)), ("cost 10 bp", dict(cost_bps=10)), ("cost 20 bp", dict(cost_bps=20))]
    for name, kw in checks:
        L.append(f"  {name}: {line(metrics(backtest(px, PAIRS, **kw)))}")
    L.append(f"  nine pairs (excluded six added): {line(metrics(backtest(px, PAIRS + EXTRA_PAIRS)))}")
    if len(t):
        L.append("  by pair: " + "; ".join(
            f"{p} {len(g)} trades, win {(g['net_pnl_pct_equity'] > 0).mean():.0%}, P&L {g['net_pnl_pct_equity'].sum():+.2%} of equity"
            for p, g in t.groupby("pair")))
        L.append(f"  hedge drift: filter z crossed zero before the frozen-hedge z on {int(t['filter_crossed_first'].sum())} "
                 f"of {len(t)} trades")
    L.append(f"  placebo 1, ICLN-URA: {line(metrics(backtest(px, [('ICLN', 'URA')])))}")
    rng = random.Random(SEED)
    sh = []
    for _ in range(PLACEBO_DRAWS):
        tk = rng.sample(OIL, 6)
        sh.append(metrics(backtest(px, [(tk[0], tk[1]), (tk[2], tk[3]), (tk[4], tk[5])]))["sharpe"])
    L.append(f"  placebo 2, {PLACEBO_DRAWS} draws of three random oil pairs: median Sharpe {np.median(sh):+.2f}; "
             f"share of draws at least as good as the main result {np.mean([x >= m['sharpe'] for x in sh]):.0%}")

    text = "\n".join(L)
    print(text)
    with open(os.path.join(out, "pairs_backtest_design.txt"), "w") as f:
        f.write(text + "\n")
    res["elig"].to_csv(os.path.join(out, "pairs_eligibility_design.csv"), index=False)
    t.to_csv(os.path.join(out, "pairs_trades_design.csv"), index=False)
    s0 = res["blocks"][0][0]
    pd.DataFrame({"date": res["days"][s0:], "daily_return": res["r"][s0:],
                  "equity": np.cumprod(1 + res["r"][s0:])}).to_csv(os.path.join(out, "pairs_equity_design.csv"), index=False)
    charts(res, out)


def charts(res, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    s0 = res["blocks"][0][0]
    d = pd.to_datetime(res["days"])
    fig, ax = plt.subplots(figsize=(9, 3.6))
    ax.plot(d[s0:], np.cumprod(1 + res["r"][s0:]), color="#1f5f99", lw=1.6)
    ax.axhline(1, color="#888", lw=0.8)
    for s, _ in res["blocks"]:
        ax.axvline(d[s], color="#ddd", lw=0.6, zorder=0)
    ax.set_title("Pairs strategy, growth of $1, design period (after costs)")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(os.path.join(out, "pairs_equity_design.png"), dpi=160)
    plt.close(fig)

    fig, axes = plt.subplots(len(res["z"]), 1, figsize=(9, 2.4 * len(res["z"])), sharex=True)
    t = res["trades"]
    for ax, (p, z) in zip(np.atleast_1d(axes), res["z"].items()):
        name = f"{p[0]}-{p[1]}"
        ax.plot(d[s0:], z[s0:], color="#1f5f99", lw=0.9)
        for y, c in ((2, "#c77c02"), (-2, "#c77c02"), (4, "#b3261e"), (-4, "#b3261e")):
            ax.axhline(y, color=c, lw=0.7, ls="--")
        ax.axhline(0, color="#888", lw=0.6)
        for s, _ in res["blocks"]:
            ax.axvline(d[s], color="#ddd", lw=0.6, zorder=0)
        if len(t):
            g = t[t["pair"] == name]
            for _, row in g.iterrows():
                fi, xi = res["days"].index(row["fill_day"]), res["days"].index(row["exit_day"])
                ax.scatter(d[fi], z[fi], marker="^" if row["dir"] > 0 else "v", color="#2e7d32", zorder=3, s=28)
                ax.scatter(d[xi], z[xi] if not np.isnan(z[xi]) else 0, marker="x", color="#b3261e", zorder=3, s=28)
        ax.set_ylabel(name)
        ax.set_ylim(-6, 6)
        ax.spines[["top", "right"]].set_visible(False)
    np.atleast_1d(axes)[0].set_title("Kalman z-score: entry at +/-2 (orange), stop at +/-4 (red); "
                                     "green = entry (up = long A), x = exit; gaps = pair not eligible")
    fig.tight_layout()
    fig.savefig(os.path.join(out, "pairs_zscores_design.png"), dpi=160)
    plt.close(fig)


# ---------------------------------------------------------------- self-test
def selftest():
    rng = np.random.default_rng(1)
    n = 755
    days = pd.bdate_range("2021-11-01", periods=n).date
    lb = np.cumsum(rng.normal(0, 0.015, n)) + 4
    u = np.zeros(n)
    for i in range(1, n):
        u[i] = 0.92 * u[i - 1] + rng.normal(0, 0.012)   # half-life about 8.3 days
    la = 0.1 + 1.0 * lb + u
    lc = np.cumsum(rng.normal(0, 0.015, n)) + 4
    px = pd.DataFrame({"A": np.exp(la), "B": np.exp(lb), "C": np.exp(lc), VIX: 20.0}, index=days)
    good = backtest(px, [("A", "B")])
    bad = backtest(px, [("C", "B")])
    ge, be = int(good["elig"]["eligible"].sum()), int(bad["elig"]["eligible"].sum())
    mg = metrics(good)
    print(f"planted pair A-B: eligible {ge}/8 blocks, {mg['trades']} trades, Sharpe {mg['sharpe']:+.2f}, "
          f"max gross {mg['max_gross']:.0%}")
    print(f"random pair C-B: eligible {be}/8 blocks, {len(bad['trades'])} trades")
    assert ge >= 6 and mg["trades"] >= 5, "planted pair not found or not traded"
    assert be <= 2, "random pair accepted too often"
    assert mg["max_gross"] <= 1.25, "daily gross drifted far above 100%"
    assert set(good["trades"]["reason"]) <= {"crossed zero", "stop-loss", "time stop", "block end"}
    print("SELFTEST PASSED")


if __name__ == "__main__":
    if sys.argv[1:] == ["--selftest"]:
        selftest()
    else:
        run(sys.argv[1], sys.argv[2])
