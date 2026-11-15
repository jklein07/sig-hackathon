"""Strategy variant 7: XLE with volatility scaling, plus a CVX/XOP pair trade. Rules: ../hypothesis-volpair.md.

Usage (from scripts/):
  python -I vol_pair.py --selftest
  python -I vol_pair.py design  ../data/prices.csv ../output
  python -I vol_pair.py heldout ../data/prices.csv ../output

Both runs refuse to start unless the rules file and this script match their frozen fingerprints.
"""
import datetime as dt
import hashlib
import math
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WINDOWS = {"design": (dt.date(2021, 11, 1), dt.date(2024, 10, 31)),
           "heldout": (dt.date(2024, 11, 1), dt.date(2026, 10, 30))}
BASE_VOL, Z_WIN, Z_IN, Z_OUT, Z_STOP = 0.20, 40, 2.0, 0.5, 4.0
COST_BPS, BORROW = 5, 0.005
TRADES_MIN = 10
FROZEN = ("hypothesis-volpair.md", "scripts/vol_pair.py")


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
                sys.exit(f"STOP: {rel} does not match its frozen fingerprint; run refused.")
    print("Fingerprints checked OK.")


def load(path, which):
    start, end = WINDOWS[which]
    df = pd.read_csv(path, encoding="utf-8-sig")
    df["Date"] = pd.to_datetime(df["Date"], format="%m/%d/%Y").dt.date
    df = df.set_index("Date")[["XLE", "CVX", "XOP"]]
    if which == "design":
        df = df[(df.index >= start) & (df.index <= end)]
    else:                                          # design history (for the first decision) + held-out days
        df = pd.concat([df[df.index <= WINDOWS["design"][1]].tail(300), df[(df.index >= start) & (df.index <= end)]])
    assert df.index[-1] <= end and df.notna().all().all()
    return df


def first_decision(px, which):
    days = list(px.index)
    month_end = [i for i in range(len(days) - 1) if days[i].month != days[i + 1].month]
    if which == "design":
        return next(i for i in month_end if i >= Z_WIN - 1)
    return max(i for i in month_end if days[i] <= WINDOWS["design"][1])


def simulate(px, d0, base_vol=BASE_VOL, z_win=Z_WIN, cost_bps=COST_BPS, mode="both", base_trailing=False):
    """mode: 'both' (the strategy), 'vol' (pair sleeve in cash), 'pair' (all capital in the pair)."""
    days = list(px.index)
    X, C, P = (px[k].to_numpy() for k in ("XLE", "CVX", "XOP"))
    n, cost = len(days), cost_bps / 1e4
    ratio = C / P
    month_end = {i for i in range(n - 1) if days[i].month != days[i + 1].month}
    prior = [m for m in month_end if m < d0]
    last_me = max(prior) if prior else max(0, d0 - 21)     # volatility for the first decision: the month before d0
    cash, hX, hC, hP = 1.0, 0.0, 0.0, 0.0
    w = None
    pend_w, pend_open, pend_close = None, None, None
    pair_dir, trade = 0, None
    trades, ws, open_days = [], [], 0
    eq = np.full(n, np.nan)
    dret = np.zeros(n)

    def decide_w(i):
        r = X[last_me + 1:i + 1] / X[last_me:i] - 1
        sig = r.std(ddof=1) * math.sqrt(252)
        if mode == "pair":
            return 0.0
        b = base_vol
        if base_trailing:
            rr = X[max(1, i - 251):i + 1] / X[max(0, i - 252):i] - 1
            b = rr.std(ddof=1) * math.sqrt(252)
        return min(1.0, b / sig)

    pend_w = decide_w(d0)
    last_me = d0
    for i in range(d0 + 1, n):
        # mark to market from i-1 to i
        prev = cash + hX + hC + hP
        if i > d0 + 1:
            rX, rC, rP = X[i] / X[i - 1] - 1, C[i] / C[i - 1] - 1, P[i] / P[i - 1] - 1
            hX *= 1 + rX
            hC *= 1 + rC
            hP *= 1 + rP
            short = -min(hC, 0) - min(hP, 0)
            cash -= short * BORROW / 252
            if trade is not None:
                trade["pnl"] += hC * rC / (1 + rC) + hP * rP / (1 + rP) - short * BORROW / 252
        E = cash + hX + hC + hP

        def trade_to(newX, newC, newP):
            nonlocal cash, hX, hC, hP
            tc = cost * (abs(newX - hX) + abs(newC - hC) + abs(newP - hP))
            cash -= (newX - hX) + (newC - hC) + (newP - hP) + tc
            if trade is not None:
                trade["pnl"] -= cost * (abs(newC - hC) + abs(newP - hP))
            hX, hC, hP = newX, newC, newP

        # fills at today's close (orders decided yesterday)
        if pend_w is not None:
            w = pend_w
            pend_w = None
            sleeve = (1 - w) * E if mode != "vol" else 0.0
            nC, nP = (pair_dir * sleeve / 2, -pair_dir * sleeve / 2) if pair_dir else (0.0, 0.0)
            trade_to(w * E if mode != "pair" else 0.0, nC, nP)
        if pend_close is not None and trade is not None:
            trade_to(hX, 0.0, 0.0)
            trade.update(exit_day=days[i], reason=pend_close, hold=i - trade["fill_i"])
            trades.append(trade)
            trade, pair_dir, pend_close = None, 0, None
        if pend_open is not None and trade is None and mode != "vol":
            E0 = cash + hX + hC + hP
            sleeve = min((1 - w) * E0, E0 - abs(hX))               # never above 100% of equity at entry
            assert abs(hX) + sleeve <= E0 * (1 + 1e-12)             # no leverage at entry (before costs)
            pair_dir = pend_open
            trade = {"dir": "long CVX / short XOP" if pair_dir > 0 else "short CVX / long XOP", "signal_day": days[i - 1],
                     "fill_day": days[i], "fill_i": i, "pnl": 0.0, "sleeve0": sleeve}
            trade_to(hX, pair_dir * sleeve / 2, -pair_dir * sleeve / 2)
        pend_open = None
        E = cash + hX + hC + hP
        eq[i] = E
        dret[i] = E / prev - 1                      # first fill day: entry cost only
        ws.append(w)
        open_days += trade is not None

        # signals at today's close
        if i == n - 1:
            break
        if i in month_end:
            pend_w = decide_w(i)
            last_me = i
        if i >= z_win - 1:
            win = ratio[i - z_win + 1:i + 1]
            z = (ratio[i] - win.mean()) / win.std(ddof=1)
            if trade is not None and (abs(z) < Z_OUT or abs(z) > Z_STOP):
                pend_close = "take profit" if abs(z) < Z_OUT else "stop-loss"
            elif trade is None and Z_IN < abs(z) <= Z_STOP:
                pend_open = 1 if z < 0 else -1
    if trade is not None:                          # close at the last close, for the trade list
        trade.update(exit_day=days[-1], reason="period end", hold=n - 1 - trade["fill_i"])
        trades.append(trade)
    r = dret[d0 + 1:]
    t = pd.DataFrame([{k: v for k, v in x.items() if k != "fill_i"} | {"return_on_sleeve": x["pnl"] / x["sleeve0"] if x["sleeve0"] else 0.0}
                      for x in trades])
    return {"r": r, "days": days[d0 + 1:], "trades": t, "avg_w": float(np.mean([x for x in ws if x is not None])),
            "open_share": open_days / max(1, n - d0 - 1),
            "completed": int((t["reason"] != "period end").sum()) if len(t) else 0}


def benchmark(px, d0):
    X = px["XLE"].to_numpy()
    return np.concatenate([[0.0], X[d0 + 2:] / X[d0 + 1:-1] - 1])     # bought at the first fill close


def stats(r):
    eq = np.cumprod(1 + r)
    sd = r.std(ddof=1)
    return {"sharpe": r.mean() / sd * math.sqrt(252) if sd > 0 else 0.0, "total": float(eq[-1] - 1),
            "vol": float(sd * math.sqrt(252)), "maxdd": float((eq / np.maximum.accumulate(eq) - 1).min())}


def fmt(s):
    return f"Sharpe {s['sharpe']:+.2f}, total {s['total']:+.2%}, volatility {s['vol']:.1%}, max drawdown {s['maxdd']:.2%}"


def run(which, prices_path, out_dir):
    check_fingerprints()
    px = load(prices_path, which)
    d0 = first_decision(px, which)
    res = simulate(px, d0)
    s, b = stats(res["r"]), stats(benchmark(px, d0))
    pair = simulate(px, d0, mode="pair")
    ps = stats(pair["r"])
    c1, c2 = s["sharpe"] > b["sharpe"], s["maxdd"] > b["maxdd"]
    c3 = ps["total"] > 0 and pair["completed"] >= TRADES_MIN
    verdict = "SUPPORTED" if c1 and c2 and c3 else "NOT SUPPORTED"
    label = "HELD-OUT PERIOD (third look at the window; pair settings were seen on the full file)" if which == "heldout" else "DESIGN PERIOD"
    L = [f"VARIANT 7: XLE volatility scaling + CVX/XOP pair. {label}",
         f"First decision {px.index[d0]}; returns {res['days'][0]} to {res['days'][-1]}. After costs (5 bp per transaction, 0.5%/yr borrow).",
         "", f"STRATEGY:        {fmt(s)}", f"XLE BENCHMARK:   {fmt(b)}",
         f"PAIR LEG ALONE:  {fmt(ps)}; completed trades {pair['completed']}",
         f"Average XLE weight {res['avg_w']:.0%}; pair trade open {res['open_share']:.0%} of days",
         "", "TESTS",
         f"  1. Sharpe above XLE's: {'yes' if c1 else 'no'} ({s['sharpe']:+.2f} vs {b['sharpe']:+.2f})",
         f"  2. Max drawdown smaller than XLE's: {'yes' if c2 else 'no'} ({s['maxdd']:.2%} vs {b['maxdd']:.2%})",
         f"  3. Pair leg alone positive after costs with >= {TRADES_MIN} trades: {'yes' if c3 else 'no'} "
         f"({ps['total']:+.2%}, {pair['completed']} trades)",
         f"  FROZEN TEST: {verdict}", "", "PAIR TRADES (pair leg alone)"]
    if len(pair["trades"]):
        L.append(pair["trades"][["dir", "signal_day", "fill_day", "exit_day", "reason", "hold", "return_on_sleeve"]]
                 .to_string(index=False, float_format=lambda v: f"{v:+.4f}"))
        L.append("  exits: " + ", ".join(f"{k} {v}" for k, v in pair["trades"]["reason"].value_counts().items()))
    L += ["", "DECLARED CHECKS (not results)",
          f"  volatility rule only (pair sleeve in cash): {fmt(stats(simulate(px, d0, mode='vol')['r']))}",
          f"  base = trailing 252-day XLE volatility: {fmt(stats(simulate(px, d0, base_trailing=True)['r']))}"]
    for zw in (20, 60):
        p2 = simulate(px, d0, z_win=zw, mode="pair")
        L.append(f"  z window {zw} days: strategy {fmt(stats(simulate(px, d0, z_win=zw)['r']))}; "
                 f"pair alone total {stats(p2['r'])['total']:+.2%}, {p2['completed']} trades")
    for c in (10, 20):
        L.append(f"  cost {c} bp: strategy {fmt(stats(simulate(px, d0, cost_bps=c)['r']))}; "
                 f"pair alone total {stats(simulate(px, d0, cost_bps=c, mode='pair')['r'])['total']:+.2%}")
    text = "\n".join(L)
    print(text)
    with open(os.path.join(out_dir, f"volpair_backtest_{which}.txt"), "w") as f:
        f.write(text + "\n")


def selftest():
    n = 800
    days = list(pd.bdate_range("2022-01-03", periods=n).date)
    rng = np.random.default_rng(7)
    x = 100 * np.cumprod(1 + rng.normal(0.0003, 0.01, n))
    p = 50 * np.cumprod(1 + rng.normal(0.0002, 0.015, n))
    ou = np.zeros(n)
    for k in range(1, n):
        ou[k] = 0.9 * ou[k - 1] + rng.normal(0, 0.02)
    c = 2 * p * np.exp(ou)                       # CVX/XOP ratio mean-reverts around 2
    px = pd.DataFrame({"XLE": x, "CVX": c, "XOP": p}, index=days)
    d0 = next(i for i in range(len(days) - 1) if days[i].month != days[i + 1].month and i >= Z_WIN - 1)
    pr = simulate(px, d0, mode="pair")
    assert pr["completed"] >= 10 and stats(pr["r"])["total"] > 0, "planted mean reversion not traded profitably"
    v = simulate(px, d0, mode="vol")
    assert v["trades"].empty and 0 < v["avg_w"] <= 1
    # calm XLE: weight 100%, vol-only strategy tracks XLE minus one entry cost
    calm = px.copy()
    calm["XLE"] = 100 * np.cumprod(1 + np.where(np.arange(n) % 2, 0.002, -0.002))   # ~3% vol
    vc = simulate(calm, d0, mode="vol")
    assert abs(vc["avg_w"] - 1) < 1e-12
    assert abs(np.prod(1 + vc["r"]) - np.prod(1 + benchmark(calm, d0)) * (1 - COST_BPS / 1e4)) < 1e-5   # monthly trims of the cash left by the entry cost
    b = simulate(px, d0)
    assert np.isfinite(b["r"]).all()
    print("selftest OK")


if __name__ == "__main__":
    if sys.argv[1] == "--selftest":
        selftest()
    else:
        run(sys.argv[1], sys.argv[2], sys.argv[3])
