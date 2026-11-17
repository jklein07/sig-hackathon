# Hypothesis: Kalman-filter pairs on three same-business pairs (strategy variant 3, version 2)

**Frozen on 2026-11-13 23:00 EST. Version 1 (`hypothesis-pairs.md`, attempt #15) had already been run on the design period: 1 trade, too few to judge.**
Nothing below may be changed after this time. Anything tried beyond it is a new, logged attempt in `attempts-log.md`.

**What changed from version 1 and why** (decided by Jon after version 1's run, on trade count only): version 1's cointegration test (p < 0.05 on 252 days) blocked 23 of 24 pair-quarters, while the Kalman signal itself fired 34 times across the three pairs (diagnostic without returns, attempt #16). Changes: (1) no cointegration p-value test; eligibility is formation half-life under 126 trading days; (2) time stop 2 × half-life capped at 30 trading days. Everything else is unchanged.

The three pairs were chosen from design-period return correlations (attempt #2).

## 1. Reason

Two companies in the same business face the same prices: the same crude price for two producers, the same refining margin for two refiners, the same mix of both for two integrated majors. Their share prices therefore share one large common driver. Company-specific news, fund flows and liquidity trades push one away from the other for a while, and the common driver pulls them back. A pairs trade bets on that pull-back while hedging the common driver out.

**Who is on the other side:** traders who need to buy or sell one particular stock now (index and sector funds rebalancing, liquidity demand after company news) and accept a price that is temporarily out of line with its closest peer. The pairs trader supplies that liquidity and is paid for waiting.

## 2. Prediction

When the gap between the two stocks (after the Kalman hedge) is more than 2 of its expected standard deviations away from normal, it tends to close within about two half-lives. Trading those gaps earns more than the costs.

## 3. Rules, fixed in advance

**Pairs**: XOM–CVX (integrated majors), COP–EOG (producers), MPC–VLO (refiners). The first stock is A, the second B. The excluded pairs and the reason for each are listed in section 6.

**Data**: adjusted daily closes from the hackathon price file (`data/prices.csv`), in logs; VIX close from the same file. Design period 2021-11-01 to 2024-10-31 only.

**Walk-forward blocks**: trading day 252 onward is cut into consecutive 63-day trading blocks (8 in the design period; the last is shortened by the end of the period). Each block's formation window is the 252 trading days before it.

**Eligibility** (per pair, per block, from the formation window only): the half-life of the formation regression spread is below 126 trading days. The half-life comes from regressing the daily change of the spread on its previous level: half-life = −ln 2 / ln(1 + slope); a pair whose spread shows no pull-back (slope ≥ 0) is not eligible. The Engle-Granger p-value is reported for information only.

**Kalman filter** (re-initialised at the start of each block, for each eligible pair):
- State: [α, β], each a random walk. Observation: log A_t = α + β · log B_t + noise.
- Starting state and its covariance: the formation-window OLS estimate of α and β and its coefficient covariance.
- Observation noise R: variance of the formation-window OLS residuals. State noise Q (per day) = the formation-window OLS coefficient covariance ÷ 252, so the hedge can drift by about one estimation error per year (a roughly 12-month memory). Fixed, not tuned.
- Why not the planned δ = 0.0001 (Chan's default): on synthetic log prices, before any real data was used, it let β drift about 1% a day and the filter absorbed almost every gap (z never above 1.1). Changed before freezing.
- Each day: predict (state unchanged, covariance + Q); prediction error e_t = log A_t − (α + β log B_t) using the predicted state; its variance S_t = H P H′ + R; **z_t = e_t / √S_t**; then update the state.

**Entry**: when |z_t| rises to 2 or more on day t after being below 2 on day t−1 (a fresh cross), and VIX is not above the 80th percentile of its previous 252 closes, enter at the close of day t+1.
- z ≥ 2 (A rich): short A, long B. z ≤ −2: long A, short B.
- The hedge is frozen at entry: α_e, β_e and S_e are the predicted state and variance that produced z_t.

**Exit**: the trade's own gap z_trade = (log A − α_e − β_e log B) / √S_e is checked at each close from the fill day on. The exit is filled at the next close after the first of:
- z_trade crosses zero (its sign changes from the entry sign, or it is exactly 0);
- |z_trade| ≥ 4 (stop-loss);
- the trade has been open for 2 × half-life trading days, rounded up, or 30 trading days, whichever is shorter (time stop).
Every trade is closed at the last close of its block. An entry whose fill would fall on the block's last day is skipped.

**Sizing**: at the start of each block, capital is split equally across the N eligible pairs. A pair's trade has gross notional (long plus short) equal to 1/N of equity at entry. The legs are split in proportion 1 : β_e (A leg 1/(1+|β_e|), B leg |β_e|/(1+|β_e|) of the pair's gross). Legs are held, not rebalanced, until exit. Long plus short at entry never exceeds 100% of equity; there is no leverage. Cash earns nothing.

**Costs**: 5 basis points of notional per transaction (each leg in and out, four per trade); short borrow at 0.5% a year on the short leg's value (an assumption). Also shown at 10 and 20 basis points.

## 4. What counts as success

Over the daily returns of the 8 design trading blocks, after costs, the strategy is **supported** only if all three hold:
1. annualised Sharpe ratio (mean daily return / standard deviation × √252, zero-return days included) of at least 0.5;
2. a positive return in at least 5 of the 8 blocks;
3. at least 10 completed trades. With fewer than 10 the result is reported as "too few to judge".

Also reported: total return, maximum drawdown, win rate, average holding period, share of days in the market.

## 5. Checks declared in advance (reported as checks, not results)

- Rolling-regression hedge: β and α fixed at the formation OLS values for the whole block; z = (spread − formation mean) / formation standard deviation.
- State noise at covariance ÷ 1008 (slower hedge) and ÷ 63 (faster hedge).
- Entry threshold 1.5 and 2.5.
- Without the VIX filter.
- With the six excluded pairs added (COP–OXY, EOG–OXY, MPC–PSX, PSX–VLO, SLB–OIH, COP–XOP): nine pairs, capital split across all eligible.
- Costs at 10 and 20 basis points.
- Results by pair and by block.
- Hedge drift: for each trade, whether the filter's own z crossed zero before the frozen-hedge z_trade did.
- Placebo 1: the same rules on ICLN–URA alone.
- Placebo 2: 200 draws of three disjoint random pairs from the 12 oil-linked tickers (fixed seed 20261113); share of draws with a Sharpe at least as high as the main result.

## 6. What could break it, and exclusions

- **Structural breaks**: refining margins surged in 2022; Berkshire bought about a quarter of OXY; XOM–Pioneer and CVX–PDC changed share counts. A pair can stop being a pair.
- **Weak filter**: without the cointegration test, the half-life test also lets a pure random-walk pair through (it did in all 8 blocks of the synthetic self-test). The strategy relies on the pairs being chosen on business grounds and on the stop-loss.
- **Second version**: rules revised after seeing version 1's design result; disclosed in the pitch.
- **Pair choice**: picked on design-period correlation (a mild selection); the nine-pair check addresses it.
- **Daily closes only**: stops are checked at the close; no intraday fills. Borrow cost is assumed.
- **Kalman settings** come from a published default, not from this data, and the Kalman hedge can absorb a real divergence; the frozen-hedge exit and the drift check address this.
- Excluded: the other same-business pairs (simplicity, no stock twice); stock-vs-ETF pairs (the ETF holds the stock); cross-business pairs (the full-period refiner-vs-producer outcome is already known, attempt #1); ICLN and URA (not oil-linked); XLE against XOM or CVX (about 40% of XLE).

**Data split**: design period only. The held-out period 2024-11-01 to 2026-10-30 is opened once, with this code unchanged, only if the team picks this strategy for its single held-out run.
