"""Reproduce the deck figures that are not printed by curve_is.py / curve_oos.py.

Run from this folder after curve_oos.py (it reads data/curve_backtest.csv):
    python -I deck_numbers.py

Prints:
  1. Average position size (Risk slide: "about half").
  2. The two example weeks (Core framework slide and the "How it works" appendix).
  3. How well our gap matches the EIA month-1 / month-4 gap (Data appendix: 0.84).
  4. Return by year, split into the long side and the short side.
"""
import numpy as np
import pandas as pd

bt = pd.read_csv("data/curve_backtest.csv", parse_dates=["Date"], index_col="Date")
px = pd.read_csv("data/cl_front_z27.csv", parse_dates=["Date"], index_col="Date").dropna()
px = px[px["CL=F"] > 0]
gap = np.log(px["CL=F"] / px["CLZ27.NYM"])
live = bt["2022-10-31":]  # first day the 252-day score exists

print("1. Average position size, 2022-10-31 to 2026-10-30")
print(f"   mean |position| = {live.position.abs().mean():.2f}")
print(f"   share of days fully long or short = {(live.position.abs() >= 0.999).mean():.0%}")

print("\n2. Example weeks (gap shown as a percent: exp(log gap) - 1)")
pct = lambda x: (np.exp(x) - 1) * 100
for day in ["2026-03-06", "2025-04-07"]:
    d = pd.Timestamp(day)
    past = gap.loc[:d].iloc[-253:-1]  # the 252 trading days before this one
    print(f"   {day}: next-month ${px.loc[d, 'CL=F']:.2f}, Dec-2027 ${px.loc[d, 'CLZ27.NYM']:.2f}, "
          f"gap {pct(gap.loc[d]):.1f}%, usual {pct(past.mean()):.1f}%, "
          f"past-year range {pct(past.min()):.1f}% to {pct(past.max()):.1f}%, score {bt.slopez[d]:.2f}")

print("\n3. Our gap vs the EIA month-1 / month-4 gap")
eia = pd.read_csv("data/curve_eia.csv", parse_dates=["Date"], index_col="Date")
both = pd.concat([gap, np.log(eia.RCLC1 / eia.RCLC4)], axis=1, keys=["ours", "eia"]).dropna()
z = (both - both.rolling(252).mean()) / both.rolling(252).std()
print(f"   overlap {both.index.min().date()} to {both.index.max().date()}")
print(f"   correlation of levels = {both.corr().iloc[0, 1]:.3f}, of 252-day scores = {z.corr().iloc[0, 1]:.3f}")

print("\n4. Return by year, and which side made it (sums of daily returns, before costs)")
yr = live.index.year
table = pd.DataFrame({
    "strategy %": live.strategy.groupby(yr).apply(lambda x: ((1 + x).prod() - 1) * 100),
    "hold OIH %": live.OIH.groupby(yr).apply(lambda x: ((1 + x).prod() - 1) * 100),
    "avg position": live.position.groupby(yr).mean(),
    "long side %": (live.position.clip(lower=0) * live.OIH).groupby(yr).sum() * 100,
    "short side %": (live.position.clip(upper=0) * live.OIH).groupby(yr).sum() * 100,
})
print(table.round(2).to_string())
