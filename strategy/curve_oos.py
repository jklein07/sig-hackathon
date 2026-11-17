"""Frozen rule from PREREG_curve.md + curve_is.py selection (IS cell: OIH, h=20, slopez, t=-2.49).
Position in OIH = clip(-slopez/2, -1, 1), rebalanced every 5th trading day, 10 bp per $ traded.
Run ONCE on OOS. Robustness checks below the line were added after and are labelled as such."""
import numpy as np, pandas as pd, statsmodels.api as sm, warnings
warnings.filterwarnings("ignore")
from curve_is import load, signals, fwd, hac
IS, OOS = slice("2021-11-01", "2024-12-31"), slice("2025-01-01", "2026-10-30")
COST = 0.0010

df = load("2026-10-30"); s = signals(df); r = df.pct_change()

def backtest(sig, tgt, sign=-1, rebal=5):
    target_pos = (sign * sig / 2).clip(-1, 1)
    pos = target_pos.copy() * np.nan
    pos.iloc[::rebal] = target_pos.iloc[::rebal]
    pos = pos.ffill()
    held = pos.shift(1)                              # decided at close t, earns t+1
    return held * r[tgt] - held.diff().abs().fillna(0) * COST, held

def stats(x):
    x = x.dropna(); a = x.mean() * 252; v = x.std() * np.sqrt(252)
    eq = (1 + x).cumprod(); dd = (eq / eq.cummax() - 1).min()
    return f"ann={a*100:+6.1f}%  vol={v*100:5.1f}%  Sharpe={a/v:+.2f}  maxDD={dd*100:6.1f}%  days={len(x)}"

def alpha(x, bench):
    d = pd.concat([x, bench], axis=1).dropna()
    m = sm.OLS(d.iloc[:, 0], sm.add_constant(d.iloc[:, 1])).fit(cov_type="HAC", cov_kwds={"maxlags": 10})
    return f"alpha={m.params.iloc[0]*252*100:+.1f}%/yr t={m.tvalues.iloc[0]:+.2f} beta={m.params.iloc[1]:+.2f}"

print("=== PRE-REGISTERED TEST ===")
for lab, sl in [("IS ", IS), ("OOS", OOS)]:
    b, t, n = hac(fwd(df.OIH, 20)[sl], s.slopez[sl], 20)
    print(f"  predictive regression OIH h=20 on slopez  {lab}: beta={b:+.4f} t={t:+.2f} n={n}")
ret, held = backtest(s.slopez, "OIH")
for lab, sl in [("IS ", IS), ("OOS", OOS)]:
    print(f"  strategy {lab}: {stats(ret[sl])}")
    print(f"           {lab}: {alpha(ret[sl], r.OIH[sl])}   avg position={held[sl].mean():+.2f}")
    print(f"  OIH B&H  {lab}: {stats(r.OIH[sl])}")

print("\n=== ROBUSTNESS (added after the pre-registered test; not used for selection) ===")
for lab, sl in [("IS ", IS), ("OOS", OOS)]:
    b, t, n = hac(fwd(df.OIH, 5)[sl], s.slopez[sl], 5); b2, t2, _ = hac(fwd(df.XOP, 20)[sl], s.slopez[sl], 20)
    print(f"  {lab}: OIH h=5 t={t:+.2f}   XOP h=20 t={t2:+.2f}")
for w in [126, 252, 504]:
    z = (df.slope - df.slope.rolling(w).mean()) / df.slope.rolling(w).std()
    x, _ = backtest(z, "OIH")
    sh = lambda q: q.dropna().mean() / q.dropna().std() * np.sqrt(252)
    print(f"  z-window {w}: Sharpe IS {sh(x[IS]):+.2f}  OOS {sh(x[OOS]):+.2f}")
x, _ = backtest(s.slopez, "XOP"); print(f"  same rule on XOP: IS {stats(x[IS])}\n                    OOS {stats(x[OOS])}")
print("\nBy calendar year (pre-registered strategy):")
print((ret.groupby(ret.index.year).apply(lambda q: (1 + q).prod() - 1) * 100).round(1).to_string())
pd.DataFrame({"strategy": ret, "position": held, "slopez": s.slopez, "OIH": r.OIH}).to_csv("data/curve_backtest.csv")
