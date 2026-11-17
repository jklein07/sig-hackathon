# Pre-registration: futures curve signals (written 2026-11-15, before any return tests)

**IS:** 2021-11-01 to 2024-12-31. **OOS:** 2025-01-01 to 2026-10-30. OOS gets run **once**, after the rule is frozen.

## Data
- `USO` (front-month WTI fund) and `USL` (12-month WTI strip fund), Yahoo adjusted close. Both close at 4pm ET, the same as the stocks.
- Slope = ln(CL=F / CLZ27.NYM): front month vs the Dec-2027 contract. Positive means backwardation. Tenor shrinks slowly over the sample, so I use z-scores against a trailing 252-day window.
- Validation only: EIA NYMEX contracts 1–4 (through 2024-04-05).

## Hypotheses (signal measured at close t; return from close t to close t+h)
- **H1 (diagnostic, same day):** Producer stocks (XOP) track the strip (USL) more than the front month (USO). Regress XOP on USL and (USO − USL). No trading.
- **H2 (front overreaction):** D_k = k-day return of USO minus USL ("the front outran the strip"). Prediction: high D_k → **lower** future returns for the target (negative coefficient). Stocks overreact to front-month moves that the strip doesn't confirm.
- **H3 (backwardation):** z(slope) against trailing 252d. Two-sided test. Prior: positive (tight physical market → producers do well).

## Grid (12 cells)
- Targets: XOP, OIH.
- H2: k ∈ {5, 20}, h ∈ {5, 20} → 8 cells.
- H3: h ∈ {5, 20} → 4 cells.
- Inference: OLS with HAC (maxlags = max(h, 5)). Family of 12 → Bonferroni two-sided α = 0.05/12 → |t| > 2.87 to call a cell significant.

## Selection rule (IS only)
- Pick the one cell with the largest IS |t| **with the pre-registered sign** (H3 can take either sign).
- Require IS |t| ≥ 2.0 **and** the neighbouring k or h cells for the same target and hypothesis to have the same sign.
- If no cell qualifies, declare the curve signals null in IS and **do not** go on to an OOS backtest.

## Backtest rule (frozen before OOS)
- Position in the target ETF = clip(sign_expected × z_t / 2, −1, 1), where z_t is the signal standardized by its trailing 252-day mean and SD.
- Rebalance weekly (every 5th trading day) to limit turnover. Cost 10 bp per $ traded.
- Report: Sharpe IS/OOS, buy-and-hold target benchmark, alpha vs target buy-and-hold (HAC t), lookback neighbours.

## Success criterion for the hackathon claim
OOS Sharpe > 0 **and** OOS alpha vs buy-and-hold > 0, with the same sign as IS. Otherwise, report as "no evidence."
