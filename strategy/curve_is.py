"""In-sample tests for PREREG_curve.md. Truncates all data at IS_END before computing anything."""
import numpy as np, pandas as pd, statsmodels.api as sm, warnings
warnings.filterwarnings("ignore")
IS_START, IS_END = "2021-11-01", "2024-12-31"

def load(cutoff):
    px = pd.read_csv("data/prices.csv", parse_dates=["Date"], index_col="Date")
    et = pd.read_csv("data/curve_etfs.csv", parse_dates=["Date"], index_col="Date")
    cl = pd.read_csv("data/cl_front_z27.csv", parse_dates=["Date"], index_col="Date")
    idx = px.index
    et, cl = et.reindex(idx).ffill(), cl.reindex(idx).ffill()
    df = pd.DataFrame(index=idx)
    for t in ["XOP", "OIH", "XLE"]: df[t] = px[t]
    df["USO"], df["USL"] = et.USO, et.USL
    df["slope"] = np.log(cl["CL=F"] / cl["CLZ27.NYM"])
    return df[:cutoff]

def signals(df):
    s = pd.DataFrame(index=df.index)
    for k in [5, 20]:
        s[f"D{k}"] = np.log(df.USO).diff(k) - np.log(df.USL).diff(k)
    s["slopez"] = (df.slope - df.slope.rolling(252).mean()) / df.slope.rolling(252).std()
    return s

def fwd(p, h):  # return from close t to close t+h
    return p.shift(-h) / p - 1

def hac(y, x, l):
    d = pd.concat([y, x], axis=1).dropna()
    m = sm.OLS(d.iloc[:, 0], sm.add_constant(d.iloc[:, 1])).fit(cov_type="HAC", cov_kwds={"maxlags": l})
    return m.params.iloc[1], m.tvalues.iloc[1], len(d)

if __name__ == "__main__":
    df = load(IS_END)
    s = signals(df)
    r = df.pct_change()
    print(f"IS window used: {df[IS_START:].index.min().date()} .. {df.index.max().date()}")

    print("\nH1 (same day): XOP_ret ~ USL_ret + (USO_ret - USL_ret)")
    X = pd.concat([r.USL, r.USO - r.USL], axis=1, keys=["strip", "front_minus_strip"])[IS_START:]
    for t in ["XOP", "OIH"]:
        m = sm.OLS(r[t][IS_START:], sm.add_constant(X), missing="drop").fit(cov_type="HAC", cov_kwds={"maxlags": 5})
        print(f"  {t}: strip beta={m.params.strip:+.2f} (t={m.tvalues.strip:+.1f})   front-minus-strip beta={m.params.front_minus_strip:+.2f} (t={m.tvalues.front_minus_strip:+.1f})  R2={m.rsquared:.2f}")

    print("\nGrid (IS). Pre-registered sign: H2 negative, H3 two-sided. Bonferroni |t|>2.87")
    rows = []
    for tgt in ["XOP", "OIH"]:
        for h in [5, 20]:
            y = fwd(df[tgt], h)[IS_START:]
            for sig in ["D5", "D20", "slopez"]:
                b, t, n = hac(y, s[sig][IS_START:], max(h, 5))
                rows.append(dict(target=tgt, h=h, signal=sig, beta=b, t=t, n=n))
    g = pd.DataFrame(rows)
    print(g.round(4).to_string(index=False))
    g.to_csv("data/curve_is_grid.csv", index=False)
