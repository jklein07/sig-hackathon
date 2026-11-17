# SIG Energy Strategy Hackathon: Team 1

Team: Riveen, Jon, Prakrit. Submission due Wed 2026-11-18, 3 pm; pitch the same evening. We may trade only the 14 tickers in the hackathon dataset (VIX is a signal only).

## Our strategy: timing OIH with the oil futures curve

Each day we compare the price of oil for next month (Yahoo `CL=F`) with oil for December 2027 (`CLZ27.NYM`). When next-month oil is unusually expensive compared with 2027 oil, the spike is not expected to last, so producers don't plan much more drilling, and OIH (a fund of drilling-services companies) has tended to lag. We short OIH then, and buy it when the gap is unusually small.

**Rules** (fixed before any test, see [`strategy/PREREG_curve.md`](strategy/PREREG_curve.md)):

1. Gap = ln(next-month price / Dec-2027 price).
2. Score z = (gap - its 252-day average) / its 252-day standard deviation.
3. Position in OIH = -z / 2, capped at 100% short or long. The rest is cash.
4. Rebalance every 5 trading days at the close. 0.10% cost per dollar traded.

**Results** (rule chosen on 2021-11-01 to 2024-12-31, then run once on 2025-01-01 to 2026-10-30):

| | Build | Test |
|---|---|---|
| Sharpe, ours / holding OIH | 0.62 / 0.42 | 0.85 / 0.87 |
| Worst drop, ours / OIH | -12% / -36% | -19% / -34% |
| Return beyond our OIH exposure (alpha), per year | +11.0% (t = 1.5) | +11.6% (t = 1.0) |

$1 grew to $1.65 versus $1.51 for holding OIH (2022-11 to 2026-10, after costs). The evidence is thin: the test covers 22 months, alpha is not significant, and the same rule on 2001-2021 data (a shorter part of the curve) showed no effect. Full write-up: [`strategy/RESULTS.md`](strategy/RESULTS.md).

## Repository

| Folder | What's in it |
|---|---|
| [`strategy/`](strategy/) | The main strategy: pre-registrations, the three scripts, data and results. Start here. |
| [`submission/`](submission/) | What we hand in: the deck (.pptx) and the one-page writeup. |
| [`research/`](research/) | Everything we tried before settling on this: eight other strategies, each tested and dropped, with their full logs. |

## Running

Python 3 with pandas, numpy, statsmodels (and xlrd for the history test). From `strategy/`:

```bash
python curve_is.py       # build period: tests the 12 combinations, picks OIH + gap
python curve_oos.py      # runs the frozen rule on the test period, writes data/curve_backtest.csv
python curve_history.py  # same rule on 2001-2021 with EIA data
python deck_numbers.py   # the remaining deck figures (examples, average position, yearly split)
```

Each script reproduces the saved files in `strategy/data/` exactly.
