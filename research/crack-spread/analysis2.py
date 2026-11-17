import numpy as np, pandas as pd, statsmodels.api as sm, warnings; warnings.filterwarnings("ignore")
s = pd.read_csv("data/signals.csv", parse_dates=["Date"], index_col="Date")
crack, spread = s.crack, s.spread
IS, OOS = slice(None,"2024-12-31"), slice("2025-01-01",None)
def hac(y,x,l):
    d=pd.concat([y,x],axis=1).dropna(); m=sm.OLS(d.iloc[:,0],sm.add_constant(d.iloc[:,1])).fit(cov_type="HAC",cov_kwds={"maxlags":l})
    return m.params.iloc[1], m.tvalues.iloc[1]
# roll noise check: biggest daily crack jumps
dc=crack.diff(); print("Largest |daily crack moves|:"); print(dc.abs().sort_values().tail(8).round(2))
print("crack level range:", crack.min().round(1), crack.max().round(1))
print("\nA) Slower horizons: crack change over past k days -> spread return over NEXT h days")
for h in [5,20]:
    fwd = spread[::-1].rolling(h).apply(lambda x: np.prod(1+x)-1, raw=True)[::-1].shift(-1)
    for k in [5,20,60]:
        sig = crack.diff(k)
        out=[f"{lab} t={hac(fwd[sl],sig[sl],h)[1]:+.2f}" for lab,sl in [("IS",IS),("OOS",OOS)]]
        print(f"  past {k:2d}d -> next {h:2d}d: "+"  ".join(out))
print("\nB) Crack LEVEL vs its 1y average (high margins not yet in earnings?) -> next h days")
for h in [5,20]:
    fwd = spread[::-1].rolling(h).apply(lambda x: np.prod(1+x)-1, raw=True)[::-1].shift(-1)
    sig = (crack - crack.rolling(252).mean())/crack.rolling(252).std()
    out=[f"{lab} t={hac(fwd[sl],sig[sl],h)[1]:+.2f}" for lab,sl in [("IS",IS),("OOS",OOS)]]
    print(f"  crack z(252) -> next {h:2d}d: "+"  ".join(out))
print("\nC) Divergence over weeks: past-20d crack change minus what refiners already did (beta-adjusted) -> next 20d")
beta = 0.0015  # ~IS same-day beta per $1
for h in [5,20]:
    fwd = spread[::-1].rolling(h).apply(lambda x: np.prod(1+x)-1, raw=True)[::-1].shift(-1)
    for k in [5,20]:
        past = spread.rolling(k).sum(); sig = beta*crack.diff(k) - past
        out=[f"{lab} t={hac(fwd[sl],sig[sl],h)[1]:+.2f}" for lab,sl in [("IS",IS),("OOS",OOS)]]
        print(f"  gap over {k:2d}d -> next {h:2d}d: "+"  ".join(out))
