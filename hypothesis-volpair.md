# Hypothesis: XLE with volatility scaling, plus a CVX/XOP pair trade (strategy variant 7)

**Frozen on 2026-11-15 16:15 EST, before any return for this strategy was computed.**
Nothing below may be changed after this time. Anything tried beyond it is a new, logged attempt in `attempts-log.md`.

**Origin, to be disclosed:** this idea comes from Riveen and Prakrit's side of the team. The CVX/XOP settings were looked at on the **full price file, 2021–2026, including the held-out years**:
- the 40-day window
- the ±2 entry, 0.5 exit and 4 stop thresholds
- the claim that gaps close halfway in about a month

The design run is a fair test of the rules as written. The held-out run is **not** a clean out-of-sample test, for two reasons:
- the pair settings may already fit those years;
- the team ran two other strategies there first (#27, #29) and has seen those results.

The held-out run is reported as a third look at the held-out window, with that caveat. This is the team's seventh strategy.

## 1. Reason

**XLE leg.** Energy stocks pay off on average over time, but their risk varies a lot. Holding less XLE when its recent volatility is high, and all of it when calm, keeps risk more even. Volatility targeting of this kind is a standard, published approach (Moreira and Muir, *Journal of Finance* 2017, from memory).

**Pair leg.** CVX and XOP both depend on the oil price, so their price ratio is fairly steady. XOP holds smaller, more oil-sensitive producers, so it overreacts to oil news, which stretches the ratio. When the stretch is unusually large (z beyond ±2), the bet is that it partly reverses. The pair is long one leg and short the other in equal dollars, so the general oil move mostly cancels out.

**Combined.** Capital taken out of XLE when it is volatile goes into the pair, a bet that does not depend on energy's direction.

## 2. Prediction

Compared with simply holding XLE, the combined strategy earns a higher return per unit of risk, with a smaller worst drawdown. The pair leg makes money on its own after costs.

## 3. Rules, fixed in advance

**Data:** adjusted daily closes for XLE, CVX and XOP from `data/prices.csv`.

**Month-end volatility rule**
- At each month-end close (the last trading day of the month), compute σ, XLE's realised volatility over the trading days since the previous month-end close: the standard deviation of daily returns × √252.
- Target XLE weight: **w = min(100%, 20% ÷ σ)**. The 20% is fixed, taken from the teammate's spec.
- Pair sleeve: **1 − w** of equity.
- Rebalanced at the next day's close.

**Pair rule (CVX/XOP)**
- Ratio r = CVX ÷ XOP.
- z = (r − its mean over the last 40 trading days) ÷ the standard deviation over the same 40 days. Both include today.
- **Open** when flat and 2 < |z| ≤ 4, at the next day's close:
  - z > 2: short CVX, long XOP.
  - z < −2: long CVX, short XOP.
- **Close** when |z| < 0.5 (take profit) or |z| > 4 (stop-loss), at the next day's close.
- A new trade can open once the pair is flat again and the open condition holds.

**Sizing**
- When a pair trade opens, the pair sleeve is (1 − w) × equity, capped at equity minus the current XLE holding (XLE may have drifted up since the rebalance). Each leg is half of the sleeve: equal dollars, long plus short equal to the sleeve.
- At each monthly rebalance, XLE is reset to w × equity. An open pair trade is reset to (1 − w) × equity split in half.
- Between rebalances, positions are held, not rebalanced.
- Unused pair capital sits in cash and earns nothing.
- Long plus short never exceeds 100% of equity at a rebalance or an entry. There is no leverage.

**Costs:** 5 basis points per transaction on the amount traded, plus 0.5% a year to borrow the short leg. Also shown at 10 and 20 basis points.

**Start:**
- **Design run:** the first decision is at the first month-end close with at least 40 trading days of history (31 Dec 2021). The run covers the design period to 2024-10-31.
- **Held-out run:** the first decision is at the last design close (2024-10-31), using design-period history only. The run covers 2024-11-01 to 2026-10-30.

Returns count from the day after the first fill.

**Benchmark:** 100% XLE bought at the first fill and held, over the same days.

## 4. What counts as success

The strategy is **supported** in a period only if all three hold:
1. the annualised Sharpe ratio (zero days included) is **higher** than the XLE benchmark's;
2. the maximum drawdown is **smaller** than the XLE benchmark's;
3. the **pair leg on its own** makes money after costs, with at least 10 completed trades. "On its own" means the same pair rule run with all capital in the pair sleeve. With fewer than 10 trades the pair leg is "too few to judge" and the strategy is not supported.

Also reported:
- total return and volatility
- the average XLE weight
- the share of time a pair trade is open
- every pair trade, with its exit reason

## 5. Checks declared in advance (reported as checks, not results)

- **Volatility rule only:** the pair sleeve held in cash. This shows what the pair adds.
- **Pair only:** the pair leg on its own (also used in test 3).
- **Base volatility** set to XLE's volatility over the previous 252 trading days instead of 20%.
- **z window** of 20 and 60 days.
- **Costs** of 10 and 20 basis points.

## 6. What could break it

- **Look-ahead in the settings.** The pair settings came from looking at the full file, held-out years included.
- **The volatility rule mostly cuts exposure.** In a strong rally like 2022, that costs return. Whether risk-adjusted return improves depends on volatility persisting from one month to the next.
- **CVX is part of XOP's world, but not part of XOP.** CVX is integrated: it refines and makes chemicals. A refining or chemicals shock can move CVX away from producers for months, so the gap can keep widening. The stop at |z| > 4 limits this.
- **The pair half is small.** Unless XLE is very volatile, w is near 100%, so the pair sleeve is small and adds little either way.
- **Daily closes only.** Borrow cost is assumed.
