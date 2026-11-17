"""Roll-cleaned crack changes. RB/HO front month expires last business day of month -> jump on first
trading day of the month. CL expires ~3 biz days before the 25th -> jump around the 19th-23rd.
Clean daily change: drop month's first trading day; on CL roll days use RB/HO legs only? Simpler and
conservative: set the daily change to NaN on (a) first trading day of each month and (b) the trading day
after the CL expiry (approximate: first trading day on/after the 20th... we detect it as the day CL's
front changes, proxied by the biggest |CL-BZ| jump in the 18th-24th window)."""
import numpy as np, pandas as pd, statsmodels.api as sm, warnings; warnings.filterwarnings("ignore")
s = pd.read_csv("data/signals.csv", parse_dates=["Date"], index_col="Date")
fu = pd.read_csv("data/futures.csv", parse_dates=["Date"], index_col="Date").reindex(s.index).ffill()
crack, spread = s.crack, s.spread
dc = crack.diff()
idx = dc.index
first_of_month = pd.Series(idx.to_period("M"), index=idx).ne(pd.Series(idx.to_period("M"), index=idx).shift())
# CL roll day: first trading day after CL expiry. CL expires 3 biz days before 25th (or prior biz day if 25th non-biz).
def cl_expiry(y, m):
    d = pd.Timestamp(y, m, 25)
    while d.weekday() >= 5: d -= pd.Timedelta(days=1)
    return (d - pd.offsets.BDay(3)).normalize()
cl_roll = pd.Series(False, index=idx)
for p in sorted(set(idx.to_period("M"))):
    e = cl_expiry(p.year, p.month); after = idx[idx > e]
    if len(after): cl_roll[after[0]] = True
roll = first_of_month | cl_roll
dcc = dc.where(~roll)
print(f"roll days removed: {roll.sum()} of {len(roll)}")
print("largest remaining |daily moves|:", dcc.abs().sort_values().dropna().tail(5).round(2).to_dict())
IS, OOS = slice(None,"2024-12-31"), slice("2025-01-01",None)
def hac(y,x,l=5):
    d=pd.concat([y,x],axis=1).dropna(); m=sm.OLS(d.iloc[:,0],sm.add_constant(d.iloc[:,1])).fit(cov_type="HAC",cov_kwds={"maxlags":l})
    return m.params.iloc[1], m.tvalues.iloc[1], len(d)
print("\nSame-day link (cleaned):")
for lab,sl in [("IS",IS),("OOS",OOS)]:
    b,t,n=hac(spread[sl],dcc[sl]); print(f"  {lab}: corr={spread[sl].corr(dcc[sl]):+.3f} beta={b*100:+.3f}%/$  t={t:+.2f}")
cum = dcc.fillna(0).cumsum()   # roll-free crack index
fwd = {h: spread[::-1].rolling(h).apply(lambda x: np.prod(1+x)-1, raw=True)[::-1].shift(-1) for h in [1,5,20]}
print("\nPredictive (cleaned): past-k crack change -> next-h spread return, t-stats")
for k in [1,5,20,60]:
    sig = cum.diff(k)
    row = "  ".join(f"h={h:2d} IS {hac(fwd[h][IS],sig[IS],max(h,5))[1]:+.2f} OOS {hac(fwd[h][OOS],sig[OOS],max(h,5))[1]:+.2f}" for h in [1,5,20])
    print(f"  k={k:2d}: {row}")
pd.DataFrame({"dcc":dcc,"crack_clean":cum,"roll":roll}).to_csv("data/crack_clean.csv")
