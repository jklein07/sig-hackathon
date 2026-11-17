# Hypothesis: bounce-back after XLE's forced sells (strategy variant 6)

**Frozen on 2026-11-15 15:16 EST, before any held-out data (prices, holdings or volumes dated after 2024-10-31) was looked at.**
Nothing below may be changed after this time. Anything tried beyond it is a new, logged attempt in `attempts-log.md`.

To be disclosed: this is the team's sixth strategy. It is **not** a fresh idea tested blind. It comes from a breakdown of variant 1 (attempt #21) after its design results were known: the reversal leg, cut by fund direction, worked on stocks the fund sold (11 of 15 right, +0.81% on average, at the 0.25-day threshold) and not on stocks it bought. That breakdown was one of eight cuts, so the design-period numbers are **in-sample and say nothing about whether it works**. Only the held-out run counts.

## 1. Reason

XLE must trade at the close on rebalance day, whatever the price. When its cap rule forces it to sell a stock, the selling pushes that stock down against the sector at the close. The buyers who absorb it demand a discount, and once the forced selling is over the price drifts back. Buying the stock at the rebalance close and shorting XLE collects that discount.

**Who is on the other side:** the fund, which has to sell at the close on a fixed day and can't wait.

**Why sells and not buys (a guess, labelled as one):** fund buys meet existing sellers more easily, and forced sells are the side that usually needs liquidity. The design data showed the difference, but did not explain it.

## 2. Prediction

Over the 5 trading days after a rebalance close, a stock the fund was forecast to sell beats XLE.

## 3. Rules, fixed in advance

**Signals**
- Forecast XLE's trade in the nine tradable index stocks (XOM, CVX, COP, EOG, OXY, SLB, MPC, PSX, VLO) on each snapshot day with `scripts/forecast_rebalance.py`, unchanged. It uses the cap rule in force: the new procedure for every held-out rebalance.
- Dates come from the S&P methodology, as in `hypothesis.md`. The rebalance day is the third Friday of March, June, September and December. The snapshot day is the second Friday through December 2024, then the Wednesday before the second Friday from March 2025.
- A stock is a signal when its forecast is a **sale of at least 0.25 days** of its median daily volume over the previous 60 trading days.
- The 0.25-day threshold was one of variant 1's declared checks. It was picked over 0.5 days because it gave more signals in the design period (15 against 5). That choice was made after seeing results.

**Trade**
- At the rebalance-day close, buy the stock and short XLE in equal dollars.
- Exit at the close **5 trading days** later. The 5 days are variant 1's frozen reversal window, kept rather than re-tuned. The design breakdown suggested day 1 alone, and that was not taken.

**Measure:** the stock's return minus XLE's return from the rebalance close to the exit close, from `data/prices.csv`.

**Cost:** 5 basis points per transaction, 4 transactions per trade (0.20%). Also shown at 10 and 20 basis points.

**Size:** capital is split equally across the signals at a rebalance, half long and half short, so long plus short is 100% of capital. Cash between trades. No leverage.

**Data split**
- Design period: 2021-11-01 to 2024-10-31. Run only to check that the code reproduces attempt #21.
- Held-out period: 2024-11-01 to 2026-10-30, which has 8 rebalances (December 2024 to September 2026). It is opened once, with this file and the script unchanged, after the team agrees to spend its held-out look here.
- The held-out inputs below are fetched as part of that one run, not before:
  - XLE and IVV quarter-end holdings from SEC N-PORT
  - snapshot-day closes
  - 60-day volumes

## 4. What counts as success (held-out run)

The strategy is **supported** only if all three hold:
1. at least **6** signals (fewer: "too few to judge");
2. the average move is at least **0.40%** before costs, which is twice the cost (the same bar as variant 1);
3. the right sign on **more than half** of the signals.

Also reported:
- every signal individually
- the average after cost
- return on capital per rebalance
- the stock side and the XLE side of each move, separately
- the run-up leg for the same signals, as a check

## 5. Checks declared in advance (reported as checks, not results)

- Threshold at 0.5 days.
- Hold of 1 and 3 days.
- Cost at 10 and 20 basis points.
- **Placebo:** the same trade on forecast sells under 0.25 days.
- **Mirror:** the same trade direction-flipped on forecast **buys** of at least 0.25 days, which the hypothesis says should not work.

## 6. What could break it

- **The pattern may be luck.** It was picked from 8 cuts of a failed strategy, and the design period had only 15 sells.
- **Rule change:** the cap rule changed in September 2024 and the snapshot day moved in 2025. Every held-out rebalance uses the new rule, which the design period tested only once (September 2024).
- **Few trades:** about 10 sells are expected in the held-out period (15 in 12 design rebalances, scaled to 8). That is a guess, not a count, so one bad week can decide the result.
- **XLE side:** under the 0.5-day rule, most of the design move came from XLE, not from the stock (+0.40% against +0.09%). A market move in the week after a rebalance can pass for a bounce.
- **Options expiry:** the rebalance day is also a major options-expiry day.
- **Merger news:** news inside the 5 days, for example the Pioneer, Hess and Marathon deals, can swamp the effect.

## Amendment 1 (before any held-out data was fetched or read)

Logged as attempt #25 and refrozen (see `output/frozen_fingerprints.txt`). Sections 1–6 above are unchanged except where this amendment replaces them.

1. **Forecast code.** Signals come from `scripts/forecast_rebalance_v2.py`, not `scripts/forecast_rebalance.py`. Version 2 imports version 1's cap rules unchanged. It changes two things:
   - **No look-ahead.** A stock gets a forecast if XLE held it at the quarter-end before the rebalance and it has a snapshot-day close. Version 1 also needed it to be held at the quarter-end after. A company that joined the S&P 500 before the snapshot is sized from its latest 10-Q or 10-K cover-page share count filed on or before the snapshot. That count is scaled by the median fraction of the other members' shares that IVV holds. Version 1 used the next quarter-end's filing.
   - **Mergers and joiners from a table.** These come from `outside/index_changes.csv`, with an SEC or S&P source for each row dated before the snapshot, instead of a hand-written Pioneer case.
   - **Missing price, no table row.** If a company held at the quarter-end before has no snapshot close and no table row, that rebalance produces no signals.
   - **Design check:** on the design period, version 2 reproduces all 108 of version 1's forecasts to 4 decimal places, so every design signal is the same. The Pioneer ratio (2.3234) and its completion date (2024-05-03) are now taken from the 8-Ks.
2. **Holiday rule.** A scheduled snapshot or rebalance day that is not a trading day moves to the last trading day before it. This affects 19 June 2026, which becomes 18 June. S&P's announced date is not looked up.
3. **Held-out inputs.** These are fetched by `scripts/fetch_heldout_inputs.py` into a separate folder, `data_heldout/`. Only the quarter-ends before each rebalance are required. The 30 Sept 2026 filing is optional and is used only for the forecast check.
