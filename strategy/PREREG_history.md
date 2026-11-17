# Pre-registration: frozen OIH curve rule on 2001–2021

Written 2026-11-15, before any OIH data from before 2021-11-01 was downloaded or looked at.

## Why
The rule was chosen on 2021-11..2024-12 and tested once on 2025-01..2026-10. That is about 4 years of signal history and one regime. This test runs the same rule on two decades none of our choices touched.

## The one forced change: the signal source
Dec-2027 WTI does not exist before 2021, and Yahoo does not keep expired contracts. The only free daily curve history is EIA's official futures settlements, months 1 to 4 (RCLC1..RCLC4, 1985-01 to 2024-04).

- Historical slope = ln(RCLC1 / RCLC4)
- In the 2021-06..2024-04 overlap, the z-score of this slope correlates 0.84 with the z-score of our live slope (ln CL=F / CLZ27).
- Days with RCLC1 <= 0 (April 2020): the slope is set to missing and the last valid value carries forward.
- EIA dates are aligned to OIH trading days with forward fill.

This measures the near part of the curve (1 vs 4 months), not 1 month vs years out. A fail here could mean the effect is not real OR that the near curve is a worse proxy. A pass is evidence for the effect.

## Frozen rule (unchanged from PREREG_curve.md / curve_oos.py)
- z = (slope − trailing 252-day mean) / trailing 252-day std
- OIH position = clip(−z / 2, −1, 1)
- Rebalance every 5th trading day, decided at close, held from next day
- 10 bp per dollar traded

## Window
First OIH trading day on Yahoo through 2021-10-29 (the day before our original in-sample period starts). No overlap with any data used before.

## Primary test (single pre-named test, family = 1)
Predictive regression: OIH 20-day forward return on z, HAC standard errors with 20 lags.
- PASS: slope coefficient negative with t <= −1.65 (one-sided 5%)
- FAIL: anything else. A positive coefficient is reported as a reversal.

## Reported regardless (not part of pass/fail)
- Strategy: annual return, vol, Sharpe, max drawdown vs OIH buy-and-hold
- Alpha vs OIH (HAC, 10 lags)
- Sub-periods: 2001–2007, 2008–2013, 2014–2021
- Calendar-year returns
- Minimum detectable effect for the primary regression
- Data checks: gaps, splits/jumps in the OIH series (the fund changed sponsor in Dec 2011)

No parameter is changed after seeing results. Any extra analysis is labeled as added afterward.
