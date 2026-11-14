# Hypothesis: distance-method pairs within the same business (strategy variant 5)

**Frozen on 2026-11-13 23:12 EST, before any return for this method was computed.**
Nothing below may be changed after this time. Anything tried beyond it is a new, logged attempt in `attempts-log.md`.

To be disclosed: this is the team's fifth strategy (`attempts-log.md`). Two earlier pairs versions (Kalman hedge, #15 and #17) used three of the same stocks, and a rolling-regression pairs check was run inside both. The method here, the distance method, had not been run on our data.

## 1. Reason

Two companies in the same business face the same prices: the same crude price for producers, the same refining margin for refiners, the same mix for the integrated majors. Over a year, their share prices tend to move together. When one temporarily runs ahead of its peer, usually because someone needs to buy or sell that one stock now (fund flows, rebalancing, a one-off news reaction), the shared business pulls the two back together. We buy the laggard, short the leader, and are paid for supplying that liquidity and waiting.

This is the standard academic pairs method: Gatev, Goetzmann and Rouwenhorst, "Pairs Trading: Performance of a Relative-Value Arbitrage Rule", *Review of Financial Studies*, 2006 (from memory). Every number below is taken from that paper or from our earlier frozen rules, not tuned on our data.

## 2. Prediction

After two same-business stocks drift apart by more than 2 standard deviations of their normal gap, the gap closes more often and by more than it widens, enough to beat costs.

## 3. Rules, fixed in advance

**Data**: adjusted daily closes (dividends included) from `data/prices.csv`. Design period 2021-11-01 to 2024-10-31 only.

**Candidates** (same business only, nine single stocks): XOM–CVX; COP–EOG, COP–OXY, EOG–OXY; MPC–VLO, MPC–PSX, PSX–VLO.

**Formation (252 trading days)**: scale each stock's price to 1 on the first formation day. A pair's **distance** is the sum over the formation days of (scaled A − scaled B)². Pick the **3 pairs with the smallest distance**. Each chosen pair's **σ** is the standard deviation of (scaled A − scaled B) over the formation days.

**Trading (126 trading days, about 6 months)**: rescale both prices to 1 at the last formation close. Gap g_t = scaled A − scaled B.
- **Open** when |g_t| > 2σ at the close of day t; filled at the close of day t+1. g > 0 (A ran ahead): short A, long B. g < 0: the reverse. Equal dollars on each side.
- **Close** when the gap's sign flips (the prices cross) at the close of day t; filled at the close of day t+1. Every open trade is closed at the last close of the trading period.
- A pair can open again after closing, within the same trading period.
- A signal whose fill would fall after the trading period's last day is ignored.

**Overlapping portfolios**: a new portfolio (formation then trading) starts every 21 trading days, from the first day with 252 days of history, as long as its full 126-day trading period fits in the design period: **18 portfolios**. Up to 6 are trading at once.

**Sizing**: capital is split into 6 equal sleeves, one per live portfolio (unused sleeves sit in cash and earn nothing). Within a portfolio each of the 3 pairs gets a third of the sleeve; an open trade puts half of that long and half short. Long plus short therefore never exceeds 100% of capital at entry; there is no leverage. Legs are held, not rebalanced, until the trade closes, so held exposure can drift above 100% while a trade is open; the largest drift is reported.

**Costs**: 5 basis points per transaction (each leg in and out); short borrow 0.5% a year on the short leg (assumption). Also shown at 10 and 20 basis points.

## 4. What counts as success

On the strategy's daily returns after costs, from the first trading day to 2024-10-31, the strategy is **supported** only if all three hold:
1. annualised Sharpe ratio (mean daily return ÷ standard deviation × √252, zero days included) of at least 0.5;
2. at least 11 of the 18 portfolios end their trading period with a positive return;
3. at least 10 completed round-trip trades (fewer: "too few to judge").

Also reported: total return, maximum drawdown, win rate, average holding period, share of time invested, results by pair.

## 5. Checks declared in advance (reported as checks, not results)

- Trigger at 1.5σ and 2.5σ.
- Costs at 10 and 20 basis points.
- Fixed three pairs every time (XOM–CVX, COP–EOG, MPC–VLO) instead of picking the closest 3.
- All 7 candidates traded every time.
- Same-day fills (no one-day wait), as in the paper's main table.
- Placebo: 200 draws of three disjoint random pairs from the 12 oil-linked tickers (seed 20261113), traded with the same rule; share of draws with a Sharpe at least as high as the main result.

## 6. What could break it

- **Gaps that never close.** The distance method has no stop-loss. A pair whose businesses split apart (a merger, a one-company shock, Berkshire buying a quarter of OXY) is held until the 6 months end. This happened often in the Kalman versions: most of their trades ended on a time limit, not a close.
- **Few independent bets.** Seven candidates, three chosen; overlapping portfolios share trades, so 18 portfolios are not 18 independent tests.
- **The published edge has shrunk** since 2006 as more people trade it.
- **Daily closes only**; borrow cost is assumed.
- **Fifth strategy tried**: the more strategies tried, the more likely one passes by luck.
