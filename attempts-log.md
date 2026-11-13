# Attempts log

Every look at the data goes here, including the ones that led nowhere. The count of strategy variants tried is reported in the pitch.

- **Design window:** 2021-11-01 to 2024-10-31. All exploring and rule-setting happens here.
- **Held-out window:** 2024-11-01 to 2026-10-30. Not opened until the rules are frozen and sent to the team with a timestamp. Opened once.
- **Rules frozen on:** 2026-11-13 11:06 EST (`hypothesis.md`).

| # | Date | Who | What was run | Window | Strategy returns seen? | Note |
|---|---|---|---|---|---|---|
| 1 | 2026-11-12 | Jon | Integrity check of `data/prices.csv` (rows, dates, blanks) | Full file | No | The first version also printed the first and last price of every column, so the full-period direction of each asset is known: 12 of 14 ended at least 1.8 times their start, URA 1.5 times, ICLN down 37%. `scripts/check_data.py` no longer prints prices. |
| 2 | 2026-11-12 | Jon | `scripts/describe_design_window.py`: volatility, correlation, sensitivity to XLE, principal components | Design | No | Output in `output/descriptive_stats_design_window.md`. No average or cumulative returns computed. |
| 3 | 2026-11-12 | Jon | Pulled XLE's 13 quarter-end holdings (2021-09-30 to 2024-09-30) from its SEC N-PORT filings; `scripts/xle_rebalance_check.py` finds which holdings were bought or sold relative to the fund | Design | No | Data in `data/sec/`, output in `output/xle_rebalance_check.txt`. Shows share counts and weights only. Three very large ConocoPhillips trades (Q4 2023, Q2 2024, Q3 2024). |
| 4 | 2026-11-12 | Jon | Daily trading volume for COP, XOM, CVX, SLB, EOG from Yahoo, 2021-11-01 to 2024-10-31; only the yearly median volume was kept | Design | No | Saved in `data/outside/median_daily_volume_shares_m.csv`. The download also contained daily prices, which were not looked at. |
| 5 | 2026-11-13 | Jon | Pulled the energy holdings of the iShares S&P 500 fund (IVV) at the same 13 quarter-ends from its SEC N-PORT filings; `scripts/natural_vs_actual_weights.py` compares natural weights with XLE's actual weights | Design | No | Data in `data/sec/ivv_energy_*.csv`, output in `output/natural_vs_actual_weights.txt`. Weights only. |
| 6 | 2026-11-13 | Jon | `scripts/fetch_snapshot_inputs.py` and `scripts/fill_missing_closes_alpaca.py`: unadjusted closes of all 23 index members on the 12 snapshot days, and 60-day median volume for the nine tradable stocks | Design | No | From Yahoo; PXD, HES, MRO, CTRA from Alpaca because Yahoo no longer serves them. Snapshot-day price levels for 19 tickers on 5 dates were printed to the screen while checking the file. |
| 7 | 2026-11-13 | Jon | `scripts/forecast_rebalance.py`: forecast of XLE's trades from snapshot-day information, checked against the actual trades from SEC holdings | Design | No | Four readings of the ambiguous old rule were run and compared on fit to actual trades (not returns). Best: smallest big company cut first, recipients held at 4.5%: 8 of 9 large trades forecast correctly, 2 false alarms, correlation 0.99. Output in `output/forecast_check.txt`. |
| 8 | 2026-11-13 11:06 EST | Jon | Hypothesis frozen in `hypothesis.md` (fingerprints in `output/frozen_fingerprints.txt`), then `scripts/backtest_design.py` run once | Design | **Yes** | Strategy variant 1. 10 signals at 4 rebalances. Run-up: right sign 5 of 10, average +0.25% before costs. Reversal: right sign 7 of 10, average +0.49%. Both legs NOT SUPPORTED by the frozen test. Random dates did as well in 35% and 26% of draws. Declared checks (cost 10/20, threshold 0.25/1.0, window 3/10, placebo) ran in the same pass. Output in `output/backtest_design.txt`. |

Forecast-model readings tried: **4** (chosen on fit to actual trades, not on returns).

Also seen outside the price file: XLE's top holdings on State Street's fund page as of 2026-11-11 (weights only).

Strategy variants tried so far: **1** (plus the six checks declared in advance in `hypothesis.md`)
