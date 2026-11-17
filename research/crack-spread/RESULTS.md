# Crack spread → refiners vs producers: plan and test results

**Idea:** Refiners (MPC, PSX, VLO) earn the crack spread, while producers (COP, EOG, OXY) earn the crude price. If refiner stocks react slowly to crack moves, crack futures should predict refiner-minus-producer returns.

**Data:** The hackathon prices (adjusted close, 2021-11-01 to 2026-10-30). Front-month NYMEX RB, HO, CL futures from Yahoo (yfinance, pulled 2026-11-15).
**Crack:** 3-2-1 = (2·RB·42 + HO·42 − 3·CL)/3, in $/bbl. Roll days are removed: the first trading day of each month (RB/HO roll) and the day after each CL expiry. That's 120 of 1255 days.
**Traded spread:** Equal-weight refiners minus equal-weight producers, daily simple returns.
**Split:** In-sample (IS) 2021-11-01 to 2024-12-31. Out-of-sample (OOS) 2025-01-01 to 2026-10-30.

## Results

| Test | IS | OOS | Verdict |
|---|---|---|---|
| Same-day: crack change vs refiner−producer return | corr +0.25, t = +6.0 | corr +0.30, t = +5.5 | **Real, robust link** |
| Next day: crack change (1/3/5/10/20d) → tomorrow's spread | \|t\| < 0.7 | \|t\| < 0.8 | No evidence of predictability |
| Weeks: past-k crack change → next 5/20d spread | mostly \|t\| < 1.4 | one cell t = −2.8, rest small | No evidence |
| Crack level z-score (1y) → next 5/20d | t ≈ 0.3–0.7 | t ≈ 0.2–0.5 | No evidence |
| 60d crack trend sign → long/short (10 bp/side costs) | Sharpe 0.66 | Sharpe 0.76 (1.09 with 1-day extra lag) | **Not credible** (see below) |
| Benchmark: always long refiners / short producers | Sharpe 0.26 | Sharpe 1.60 | |
| Timing alpha of the 60d rule vs that benchmark | +13.9%/yr, t = 1.02 | −10.9%/yr, t = −0.68 | No timing skill shown |

### Why the 60d rule doesn't count as an edge
- **Look-ahead in model choice:** I chose k=60 after seeing IS *and* OOS t-stats (`analysis3.py` prints both). The OOS figure is not clean.
- **Lookback fragility:** IS Sharpe by lookback is 20d −0.22, 40d +0.24, 60d +0.66, 90d +0.10, 120d +0.01. The 60d result is a spike, not a plateau.
- **OOS profit is mostly exposure, not timing:** The rule was long refiners 83% of OOS days, during a stretch when refiners beat producers by 42%/yr (record 2026 cracks). Its timing alpha against static exposure is negative.
- **Statistical power:** Block-bootstrap full-sample Sharpe 5–95% range is −0.01 to 1.52, from roughly 20 cells scanned with no multiple-testing correction.

### What the nulls can and can't say
With about 795 IS days, the smallest daily predictive correlation detectable at 80% power is about 0.10 (≈ 2.8/√n). The economically useful range for a daily signal is 0.02–0.05, so these tests can't rule out a small edge. The right wording is "no evidence of predictability," not "the market is efficient here." The 5-year window also covers a single regime, the 2022 and 2026 supply shocks.

## Bottom line
- **Solid:** Crack moves explain refiner-vs-producer returns on the *same day*. This is useful for hedging, risk decomposition, and explaining performance.
- **Not supported:** Crack futures *predicting* those returns at daily-to-monthly horizons in this window. The market appears to price crack moves within the day.

## Files
- `analysis.py`: crack build, same-day test, momentum and divergence tests (uncleaned)
- `analysis2.py`: slower horizons, level and gap signals
- `analysis3.py`: roll-cleaned crack, same-day and predictive tests
- `backtest.py`: 60d trend rule backtest, benchmarks, lookback robustness
- `data/`: prices.csv (hackathon copy), futures.csv (Yahoo), signals.csv, crack_clean.csv, backtest_returns.csv

---

