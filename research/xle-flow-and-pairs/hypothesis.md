# Hypothesis: XLE rebalance trades

**Frozen on 2026-11-13, before any return around a rebalance was computed.**
Nothing below may be changed after this date. Anything tried beyond it is logged in `attempts-log.md` as a separate attempt.

## 1. Reason

XLE must trade to match its index after the close on each quarterly rebalance day, whatever the price. Its index limits how large any company may be, so when a company crosses a limit the fund is forced to buy or sell a known amount on a known day. Whoever takes the other side of a trade that large demands a better price. The stock should therefore be pushed in the direction of the fund's trade going into the rebalance, and drift back afterwards.

## 2. Predictions

- **Run-up.** From the close of the first trading day after the snapshot day to the close of the rebalance day, a stock the fund must buy beats XLE and a stock it must sell lags XLE.
- **Reversal.** Over the 5 trading days after the rebalance close, part of that move reverses.

The two predictions are tested and reported separately.

## 3. Rules, fixed in advance

**Dates** (from the S&P U.S. Indices Methodology, Select Sector Indices section)
- Rebalance day: third Friday of March, June, September and December.
- Snapshot day: second Friday of the same month through December 2024; the Wednesday before the second Friday from March 2025.

**Signal**
- On the snapshot day, forecast the fund's trade in each of the nine stocks that are both in the index and in the hackathon dataset (XOM, CVX, COP, EOG, OXY, SLB, MPC, PSX, VLO), using `scripts/forecast_rebalance.py`.
- The forecast uses only information available on the snapshot day: share counts and fund holdings from the previous quarter-end filings, and snapshot-day closing prices.
- Cap rule: the old procedure through the June 2024 rebalance (reading: smallest big company cut first, recipients held at 4.5%), the new procedure from September 2024.
- A stock is a signal when the forecast trade is at least **0.5 days** of its median daily volume over the previous 60 trading days.

**Trades**
- Run-up leg: enter at the close of the first trading day after the snapshot day, exit at the rebalance close. Long the stock and short XLE if the fund is forecast to buy; the reverse if it is forecast to sell.
- Reversal leg: enter at the rebalance close, exit at the close **5 trading days** later, in the opposite direction to the fund's forecast trade.
- Equal dollars long and short.

**Measure**: the stock's return minus XLE's return over the same days, from the hackathon price file.

**Cost**: 5 basis points per transaction, four transactions per leg (20 basis points per leg). Also shown at 10 and 20.

**Size**: capital is split equally across the signals at a rebalance, half long and half short, so long plus short never exceeds 100% of capital. Cash between rebalances.

**Data split**: design period 2021-11-01 to 2024-10-31; held-out period 2024-11-01 to 2026-10-30, opened once with this code unchanged.

## 4. What counts as failure

Each leg is judged separately, and every signal is reported individually. A leg is **not supported** if either:
- the sign is wrong on more than one signal, or
- the average move is smaller than twice the cost of the leg (40 basis points).

With this few signals the result cannot be statistically conclusive either way.

## 5. Checks declared in advance (reported as checks, not as results)

- Signal threshold at 0.25 and 1.0 days; reversal window at 3 and 10 days; cost at 10 and 20 basis points.
- Placebo: the same legs on stocks whose forecast trade is under 0.25 days.
- Random dates: each signal's legs moved to random dates in the design period (10,000 draws), to see how often chance alone does as well.

## 6. What could break it

- The trimming rule changed in September 2024 and the snapshot day moved in 2025, so the design period mostly tests the old rule and the held-out period the new one.
- Professionals may trade it earlier than the snapshot day.
- The rebalance day is also a major options-expiry day, which adds noise at the close.
- Company news can land inside the window.
- Signals at the same rebalance are not independent of each other.
