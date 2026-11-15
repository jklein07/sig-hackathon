# SIG Energy Strategy Hackathon: Team 1

Due Wed 2026-11-18, 3 pm. Team: Riveen, Jon, Prakrit. Trades only the 14 tickers in `data/prices.csv`. VIX is used as a signal only; no leverage.

**Chosen strategy: distance-method pairs (variant 5).**

## Ground rules

- **Design window:** 2021-11-01 to 2024-10-31. All exploring and back-testing so far happened here.
- **Held-out window:** 2024-11-01 to 2026-10-30. **Not opened yet.** It is run once, with the chosen strategy's code unchanged.
- **Logging:** every look at the data is recorded in [attempts-log.md](attempts-log.md).
- **Freezing:** rules files are locked before their back-test runs. Their SHA-256 fingerprints are in `output/frozen_fingerprints.txt`, so frozen files stay at these paths and are never edited.

## Strategies tested (all on the design window)

| # | Strategy | Rules (frozen) | Code | Main output | Result |
|---|---|---|---|---|---|
| 1 | Trade ahead of XLE's quarterly cap rebalance | `hypothesis.md` | `scripts/forecast_rebalance.py`, `scripts/backtest_design.py` | `output/backtest_design.txt` | Not supported |
| 2 | Index funds sell heavy-buyback stocks at S&P's quarterly share update (C2b) | `hypothesis-c2.md` | `scripts/c2_forecast_shrink.py --float`, `scripts/c2_backtest_design.py` | `output/c2_backtest_design.txt` | Not supported |
| 3 | Kalman-filter pairs, v1 | `hypothesis-pairs.md` | `scripts/pairs_kalman.py` | `output/pairs_backtest_design.txt` | Too few trades (1) |
| 4 | Kalman-filter pairs, v2 (no cointegration test) | `hypothesis-pairs-v2.md` | `scripts/pairs_kalman_v2.py` | `output/pairs_v2_backtest_design.txt` | Not supported (Sharpe −0.12) |
| 5 | **Distance-method pairs** (Gatev et al. 2006) | `hypothesis-distance.md` | `scripts/pairs_distance.py` | `output/distance_backtest_design.txt` | **Chosen.** Sharpe +0.21, 27 trades |
| 6 | Bounce-back after XLE's forced sells (from a breakdown of #1, `scripts/diag_flow_legs.py`) | `hypothesis-sells-reversal.md` (with Amendment 1) | `scripts/forecast_rebalance_v2.py`, `scripts/sells_reversal.py`; held-out inputs: `scripts/fetch_heldout_inputs.py` | `output/sells_reversal_design.txt` | In-sample only (found on the design data); held-out not run |

## Folders

- `data/`: the hackathon prices (`prices.csv`, `dataset_readme.csv`).
  - `data/sec/`: SEC data. Fund holdings (XLE, IVV), company share counts, and Berkshire's CVX and OXY stakes.
  - `data/outside/`: other non-price inputs (rebalance calendar, volumes, snapshot-day closes).
- `scripts/`: one script per step. Each script's header says how to run it.
- `output/`: results and charts. The file-name prefix gives the strategy: `distance_`, `pairs_`, `pairs_v2_`, `c2_` / `c2b_`. Unprefixed files belong to the XLE strategy.

## Running

Use the SIG virtual environment (`Scarlet-Investment-Group/.venv`) with `python -I`. For example, from `scripts/`:

```bash
../../Scarlet-Investment-Group/.venv/bin/python -I pairs_distance.py --selftest
```
