"""Descriptive statistics on the DESIGN window only.

Usage: python -I describe_design_window.py <prices.csv> <output.md>

Computes volatility, correlation, sensitivity to XLE and principal components.
It computes no average returns, no cumulative returns and no strategy results.
Rows after DESIGN_END are dropped before anything is calculated.
"""
import sys

import numpy as np
import pandas as pd

DESIGN_START = "2021-11-01"
DESIGN_END = "2024-10-31"
TRADING_DAYS = 252

GROUPS = {
    "Integrated": ["XOM", "CVX"],
    "Producers": ["COP", "EOG", "OXY", "XOP"],
    "Services": ["SLB", "OIH"],
    "Refiners": ["MPC", "PSX", "VLO"],
    "Sector ETF": ["XLE"],
    "Non-oil": ["ICLN", "URA"],
}
ORDER = [t for members in GROUPS.values() for t in members]


def md_table(df, fmt="{:.2f}", index_name=""):
    cols = [index_name] + [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for idx, row in df.iterrows():
        cells = [fmt.format(v) if isinstance(v, (float, np.floating)) else str(v) for v in row]
        lines.append("| " + " | ".join([str(idx)] + cells) + " |")
    return "\n".join(lines)


def main(prices_path, out_path):
    px = pd.read_csv(prices_path, encoding="utf-8-sig")
    px["Date"] = pd.to_datetime(px["Date"], format="%m/%d/%Y")
    px = px.set_index("Date").sort_index().loc[DESIGN_START:DESIGN_END]
    vix_col = next(c for c in px.columns if c.startswith("VIX"))
    assets = px.drop(columns=[vix_col])[ORDER]

    # Simple daily return, same definition as the dataset's Daily Returns sheet.
    rets = assets.pct_change().dropna()
    first, last, n = rets.index[0].date(), rets.index[-1].date(), len(rets)

    # 1. Annualised volatility by calendar year and for the whole window.
    vol = rets.groupby(rets.index.year).std().T * np.sqrt(TRADING_DAYS) * 100
    vol["All"] = rets.std() * np.sqrt(TRADING_DAYS) * 100
    days = rets.groupby(rets.index.year).size()

    # 2. Correlation of daily returns.
    corr = rets.corr()
    off_diag = corr.values[np.triu_indices(len(corr), k=1)]
    oil = [t for t in ORDER if t not in GROUPS["Non-oil"]]
    oil_corr = corr.loc[oil, oil].values[np.triu_indices(len(oil), k=1)]

    # 3. Sensitivity to XLE: slope and R-squared of a one-variable regression.
    xle = rets["XLE"]
    beta = pd.DataFrame(
        {
            "Beta to XLE": [rets[t].cov(xle) / xle.var() for t in ORDER if t != "XLE"],
            "R-squared": [rets[t].corr(xle) ** 2 for t in ORDER if t != "XLE"],
        },
        index=[t for t in ORDER if t != "XLE"],
    )

    # 4. Principal components of the correlation matrix.
    eigval, eigvec = np.linalg.eigh(corr.values)
    order = np.argsort(eigval)[::-1]
    eigval, eigvec = eigval[order], eigvec[:, order]
    share = eigval / eigval.sum() * 100
    for k in range(3):  # fix the arbitrary sign so the largest loading is positive
        if eigvec[np.argmax(np.abs(eigvec[:, k])), k] < 0:
            eigvec[:, k] *= -1
    loadings = pd.DataFrame(eigvec[:, :3], index=ORDER, columns=["PC1", "PC2", "PC3"])

    out = [
        "# Descriptive statistics, design window only",
        "",
        f"Returns from {first} to {last} ({n} daily returns). Source: `data/prices.csv`.",
        "Nothing after 2024-10-31 is used. No average or cumulative returns are computed.",
        "",
        "## 1. Annualised volatility (%)",
        "",
        "Standard deviation of daily returns times the square root of 252.",
        "Days per column: " + ", ".join(f"{y}: {d}" for y, d in days.items()) + f", All: {n}.",
        "",
        md_table(vol, "{:.1f}", "Ticker"),
        "",
        "## 2. Correlation of daily returns",
        "",
        f"Average of all {len(off_diag)} pairs: {off_diag.mean():.2f}. "
        f"Average of the {len(oil_corr)} pairs among the 12 oil-linked assets: {oil_corr.mean():.2f}.",
        "",
        md_table(corr, "{:.2f}", ""),
        "",
        "## 3. Sensitivity to XLE",
        "",
        "Slope and R-squared from regressing each asset's daily return on XLE's.",
        "XLE holds several of these stocks, so part of each figure is the stock measured against itself.",
        "",
        md_table(beta, "{:.2f}", "Ticker"),
        "",
        "## 4. Principal components",
        "",
        "Share of total variance of the 14 standardised return series: "
        + ", ".join(f"PC{k + 1} {share[k]:.1f}%" for k in range(5))
        + ".",
        "",
        md_table(loadings, "{:.2f}", "Ticker"),
        "",
    ]
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    print("\n".join(out))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
