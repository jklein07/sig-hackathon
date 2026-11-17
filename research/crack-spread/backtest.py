"""Pre-specified rule (chosen from IS evidence: 60d crack trend had consistent positive sign).
Position_t = sign(roll-clean crack change over past 60 trading days), measured at close t.
+1 = long MPC/PSX/VLO, short COP/EOG/OXY (equal weight, $1 each side). -1 = reverse.
Earns spread return on t+1 (lag=0) or t+2 (lag=1, extra delay for safety).
Cost: 10 bp per $1 traded per side (a flip trades $2 per side -> 40bp)."""
import numpy as np, pandas as pd
s = pd.read_csv("data/signals.csv", parse_dates=["Date"], index_col="Date")
c = pd.read_csv("data/crack_clean.csv", parse_dates=["Date"], index_col="Date")
px = pd.read_csv("data/prices.csv", parse_dates=["Date"], index_col="Date")
spread = s.spread; COST = 0.0010
def stats(r):
    r = r.dropna(); ann = r.mean()*252; vol = r.std()*np.sqrt(252)
    eq = (1+r).cumprod(); dd = (eq/eq.cummax()-1).min()
    return f"ann={ann*100:+6.1f}%  vol={vol*100:5.1f}%  Sharpe={ann/vol:+.2f}  maxDD={dd*100:6.1f}%  days={len(r)}"
def run(pos, lag):
    p = pos.shift(1+lag)                       # position held over day t
    turn = p.diff().abs().fillna(0)            # units of $1-per-side flipped
    return p*spread - turn*2*COST
periods = {"IS 2021-11..2024-12": slice(None,"2024-12-31"), "OOS 2025-01..2026-10": slice("2025-01-01",None), "FULL": slice(None,None)}
res = {}
for k in [60]:
    pos = np.sign(c.crack_clean.diff(k))
    for lag in [0,1]:
        r = run(pos, lag); res[f"k{k}_lag{lag}"] = r
        print(f"\n60d crack-trend rule, lag={lag}  (flips/yr={pos.diff().abs().gt(0).sum()/5:.0f})")
        for n,sl in periods.items(): print(f"  {n:22s} {stats(r[sl])}")
print("\nBenchmarks")
bh = spread.shift(0)
for n,sl in periods.items(): print(f"  always long refiners/short producers  {n:22s} {stats(spread[sl])}")
for n,sl in periods.items(): print(f"  XLE buy & hold                        {n:22s} {stats(px.XLE.pct_change()[sl])}")
# robustness: neighbouring lookbacks (not chosen, just to see if 60 is a lucky spike)
print("\nRobustness: other lookbacks, lag=0, Sharpe IS / OOS")
for k in [20,40,60,90,120]:
    r = run(np.sign(c.crack_clean.diff(k)),0)
    sh = lambda x: x.dropna().mean()/x.dropna().std()*np.sqrt(252)
    print(f"  k={k:3d}: IS {sh(r[:'2024-12-31']):+.2f}  OOS {sh(r['2025-01-01':]):+.2f}")
# yearly breakdown
r = res["k60_lag0"]; print("\nBy calendar year (lag=0):"); print((r.groupby(r.index.year).apply(lambda x:(1+x).prod()-1)*100).round(1).to_string())
pd.DataFrame(res).assign(spread=spread).to_csv("data/backtest_returns.csv")
