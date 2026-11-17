"""Frozen OIH curve rule on 2001-02-26..2021-10-29. Spec: PREREG_history.md. Run once."""
import numpy as np, pandas as pd, statsmodels.api as sm, warnings
warnings.filterwarnings("ignore")
COST, END = 0.0010, "2021-10-29"

def eia(k):
    x = pd.read_excel(f"data/eia/{k}.xls", sheet_name="Data 1", skiprows=2)
    x.columns = ["Date", k]
    return x.set_index("Date")[k]

c1, c4 = eia("RCLC1"), eia("RCLC4")
cv = pd.concat([c1, c4], axis=1).dropna()
slope = np.log(cv.RCLC1.where(cv.RCLC1 > 0) / cv.RCLC4).ffill()
z_eia = (slope - slope.rolling(252).mean()) / slope.rolling(252).std()   # z on EIA's own trading days

oih = pd.read_csv("data/oih_hist.csv", parse_dates=["Date"], index_col="Date").OIH[:END]
z = z_eia.reindex(oih.index.union(z_eia.index)).ffill().reindex(oih.index)
r = oih.pct_change()

def backtest(sig, rebal=5):
    tgt = (-sig / 2).clip(-1, 1)
    pos = tgt * np.nan; pos.iloc[::rebal] = tgt.iloc[::rebal]; pos = pos.ffill()
    held = pos.shift(1)
    return held * r - held.diff().abs().fillna(0) * COST, held

def stats(x):
    x = x.dropna(); a = x.mean() * 252; v = x.std() * np.sqrt(252)
    eq = (1 + x).cumprod(); dd = (eq / eq.cummax() - 1).min()
    return dict(ann=a, vol=v, sharpe=a / v, maxdd=dd, growth=eq.iloc[-1], days=len(x))

def fmt(d): return f"ann={d['ann']*100:+6.1f}%  vol={d['vol']*100:5.1f}%  Sharpe={d['sharpe']:+.2f}  maxDD={d['maxdd']*100:6.1f}%  $1->{d['growth']:.2f}"

def alpha(x):
    d = pd.concat([x, r], axis=1).dropna()
    m = sm.OLS(d.iloc[:, 0], sm.add_constant(d.iloc[:, 1])).fit(cov_type="HAC", cov_kwds={"maxlags": 10})
    return m.params.iloc[0] * 252, m.tvalues.iloc[0], m.params.iloc[1]

def predreg(sl):
    y = (oih.shift(-20) / oih - 1)[sl]
    d = pd.concat([y, z[sl]], axis=1).dropna()
    m = sm.OLS(d.iloc[:, 0], sm.add_constant(d.iloc[:, 1])).fit(cov_type="HAC", cov_kwds={"maxlags": 20})
    return m.params.iloc[1], m.tvalues.iloc[1], m.bse.iloc[1], len(d)

print(f"Window {oih.index.min().date()}..{oih.index.max().date()}  days={len(oih)}  z missing={z.isna().sum()}")
print(f"z: mean={z.mean():+.2f} sd={z.std():.2f}  share |z|>2: {(z.abs()>2).mean():.1%}")

b, t, se, n = predreg(slice(None))
print("\n=== PRIMARY (pre-registered) ===")
print(f"OIH 20d fwd ~ z: beta={b:+.4f} t={t:+.2f} n={n}  ->  {'PASS' if (b<0 and t<=-1.65) else 'FAIL'}")
print(f"MDE (80% power, one-sided 5%): |beta| >= {(1.645+0.8416)*se:.4f}   [live-period IS beta for comparison is in curve_is_grid.csv]")

ret, held = backtest(z)
print("\n=== STRATEGY (reported, not pass/fail) ===")
print("strategy:", fmt(stats(ret)))
print("OIH B&H: ", fmt(stats(r)))
a, at, ab = alpha(ret); print(f"alpha vs OIH={a*100:+.1f}%/yr t={at:+.2f} beta={ab:+.2f}  avg pos={held.mean():+.2f}  avg |pos|={held.abs().mean():.2f}")

print("\nSub-periods:")
for lab, sl in [("2001-2007", slice("2001", "2007")), ("2008-2013", slice("2008", "2013")), ("2014-2021", slice("2014", END))]:
    bb, tt, _, nn = predreg(sl); s1, s2 = stats(ret[sl]), stats(r[sl]); aa, aat, _ = alpha(ret[sl])
    print(f"  {lab}: reg beta={bb:+.4f} t={tt:+.2f} | strat Sharpe={s1['sharpe']:+.2f} DD={s1['maxdd']*100:5.1f}% | OIH Sharpe={s2['sharpe']:+.2f} DD={s2['maxdd']*100:5.1f}% | alpha={aa*100:+.1f}% t={aat:+.2f}")

yr = pd.DataFrame({"strategy": ret.groupby(ret.index.year).apply(lambda q: (1+q).prod()-1),
                   "OIH": r.groupby(r.index.year).apply(lambda q: (1+q).prod()-1),
                   "avg_pos": held.groupby(held.index.year).mean()})
print("\nCalendar years (%):"); print((yr*[100,100,1]).round(1).to_string())
pd.DataFrame({"strategy": ret, "position": held, "z": z, "OIH": r}).to_csv("data/curve_history_backtest.csv")
