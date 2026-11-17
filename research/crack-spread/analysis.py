"""SIG Energy Hackathon - crack spread -> refiners vs producers.

Signal data: NYMEX RBOB (RB=F), ULSD/heating oil (HO=F), WTI (CL=F) front-month from Yahoo.
Traded: MPC, PSX, VLO (long/short) vs COP, EOG, OXY.
In-sample (IS): 2021-11-01 .. 2024-12-31   Out-of-sample (OOS): 2025-01-01 .. 2026-10-30
"""
import numpy as np, pandas as pd, statsmodels.api as sm

IS_END = "2024-12-31"
REF, PROD = ["MPC", "PSX", "VLO"], ["COP", "EOG", "OXY"]

px = pd.read_csv("data/prices.csv", parse_dates=["Date"], index_col="Date")
fu = pd.read_csv("data/futures.csv", parse_dates=["Date"], index_col="Date")
fu = fu.reindex(px.index).ffill()          # align futures to stock trading days

# 3-2-1 crack in $/bbl (RB, HO quoted $/gal)
crack = (2 * fu["RB=F"] * 42 + fu["HO=F"] * 42 - 3 * fu["CL=F"]) / 3
r = px.pct_change()
spread = r[REF].mean(1) - r[PROD].mean(1)  # daily refiner-minus-producer return
fwd1 = spread.shift(-1)                    # tomorrow's spread return (trade at today's close)

def hac(y, x, lags=5):
    d = pd.concat([y, x], axis=1).dropna()
    m = sm.OLS(d.iloc[:, 0], sm.add_constant(d.iloc[:, 1])).fit(cov_type="HAC", cov_kwds={"maxlags": lags})
    return m.params.iloc[1], m.tvalues.iloc[1], len(d)

def split(s):
    return s[:IS_END], s[pd.Timestamp(IS_END) + pd.Timedelta(days=1):]

print("=" * 70, "\n1) Does the crack spread move refiners vs producers at all? (same day)")
dcrack = crack.diff()
for name, (a, b) in {"IS": split(spread), "OOS": split(spread)}.items():
    pass
for lab, sl in [("IS", slice(None, IS_END)), ("OOS", slice("2025-01-01", None))]:
    b, t, n = hac(spread[sl], dcrack[sl])
    c = spread[sl].corr(dcrack[sl])
    print(f"  {lab}: corr={c:+.3f}  beta={b*100:+.3f}% per $1 crack move  t={t:+.2f}  n={n}")

print("=" * 70, "\n2) Momentum: does a crack move over the last k days predict TOMORROW's spread?")
for k in [1, 3, 5, 10, 20]:
    sig = crack.diff(k)
    row = []
    for lab, sl in [("IS", slice(None, IS_END)), ("OOS", slice("2025-01-01", None))]:
        b, t, n = hac(fwd1[sl], sig[sl])
        row.append(f"{lab} t={t:+.2f}")
    print(f"  k={k:2d}: " + "  ".join(row))

print("=" * 70, "\n3) Catch-up / divergence: are refiners mispriced vs where the crack says they should be?")
# rolling regression of log(refiner/producer price ratio) on crack level; residual = mispricing
ratio = np.log(px[REF].mean(1) / px[PROD].mean(1))
rel = np.log((1 + spread).cumprod())       # cumulative relative performance (rebalanced daily)
def rolling_resid(y, x, w):
    out = pd.Series(np.nan, index=y.index)
    yv, xv = y.values, x.values
    for i in range(w, len(y)):
        ys, xs = yv[i - w:i + 1], xv[i - w:i + 1]
        if np.isnan(ys).any() or np.isnan(xs).any(): continue
        bb = np.polyfit(xs, ys, 1)
        res = ys - np.polyval(bb, xs)
        out.iloc[i] = res[-1] / res.std()
    return out
results3 = {}
for w in [20, 60, 120]:
    z = rolling_resid(rel, crack, w)
    results3[w] = z
    row = []
    for lab, sl in [("IS", slice(None, IS_END)), ("OOS", slice("2025-01-01", None))]:
        b, t, n = hac(fwd1[sl], z[sl])
        row.append(f"{lab} b={b*1e4:+.1f}bp t={t:+.2f}")
    print(f"  window={w:3d}: " + "  ".join(row) + "   (negative b = refiners catch down/up to crack)")

# save for backtest
pd.DataFrame({"crack": crack, "spread": spread, "fwd1": fwd1,
              **{f"z{w}": z for w, z in results3.items()},
              **{f"dc{k}": crack.diff(k) for k in [1, 3, 5, 10, 20]}}).to_csv("data/signals.csv")
