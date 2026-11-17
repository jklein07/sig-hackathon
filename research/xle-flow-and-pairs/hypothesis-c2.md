# Hypothesis C2b: index funds sell into buybacks and float cuts (strategy variant 2)

**Frozen on 2026-11-13 22:35 EST, before any return around a share-update date was computed for this strategy.**
Nothing below may be changed after this time. Anything tried beyond it is a new, logged attempt in `attempts-log.md`.

To be disclosed: the forecast's go/no-go check passed only after criterion (a) was rewritten having seen the result (attempts #10 to #12).

## 1. Reason

S&P updates each S&P 500 member's index share count once a quarter, after the close on the third Friday of March, June, September and December. It uses share counts from public filings dated on or before a reference date five weeks earlier, and sends the new counts to subscribers after the close on the first Friday, two weeks ahead (S&P Equity Indices Policies & Practices, "Rebalancing Guidelines – Share/IWF Reference Date & Freeze Period", printed p.16, same wording in the August 2021, April 2023 and April 2024 editions). Shares held by strategic holders are left out of the index count; open-market changes in those holdings are applied at the annual float review in September (timing from memory of S&P's Float Adjustment Methodology, not re-read; consistent with IVV's holdings).

Every index fund must then sell, at that one close, each stock's cut in excess of the average cut. Index funds are judged on matching the index, so they trade at the close whatever the price. Other traders can sell those stocks first and buy them back from the funds at the close.

## 2. Predictions

- **Before-window.** From the close of the first Friday of the update month to the close of the update (third Friday), the stocks with the largest forecast cut lag the stocks with the smallest.
- **After-window.** Over the same number of trading days after the update close, the same stocks lead.

The two are tested and reported separately.

## 3. Rules, fixed in advance

**Dates**: the 12 update days 17 Dec 2021 to 20 Sep 2024. Entry at the first-Friday close (two weeks before); before-window = trading days from entry to update (10, or 9 with a holiday); after-window = the same count after the update.

**Signal** (`scripts/c2_forecast_shrink.py --float`, output `output/c2b_signals.csv`):
- Shares: SEC cover-page shares outstanding, latest filing filed on or before the reference date, against the latest filed on or before the previous reference date.
- Float: Berkshire Hathaway's latest disclosed stake in CVX and OXY (13F or Form 4, filed on or before the reference date) is subtracted at September updates; other quarters keep last September's stake.
- Cut ("shrink") = 1 − new index shares / old index shares.
- Dropped: no new information; share count rose (merger share issues); tender offer in the interval.
- Weights proportional to (mean shrink of stocks still in − stock's shrink); longs sum to +50% of capital, shorts to −50%. Dates without at least one long and one short are skipped. This leaves 9 dates; all March dates drop out.

**Measure**: spread = (weighted return of the long side) − (weighted return of the short side), each side's weights scaled to sum to 1, from the adjusted closes in the hackathon price file. Positive spread in the before-window, and negative in the after-window, mean the prediction was right. Results are reported signed so that positive = right.

**Cost**: 5 basis points per transaction; four transactions per leg (enter and exit each side), so 20 basis points of spread per leg. Also shown at 10 and 20 basis points per transaction.

**Size**: 50% long, 50% short, so long plus short never exceeds 100% of capital. Return on capital = half the spread. Cash outside the windows.

**Data split**: design period 2021-11-01 to 2024-10-31 only. The held-out period is not opened unless the team chooses this strategy for its single held-out run.

## 4. What counts as failure

Each window is judged separately. A window is **not supported** if either:
- the sign is wrong on more than one of the 9 dates (8 or 9 right happens by chance about 2% of the time), or
- the average signed spread is smaller than 40 basis points (twice the cost of a leg).

With 9 dates and MPC carrying most of the short side on most dates, the result cannot be conclusive either way.

## 5. Checks declared in advance (reported as checks, not results)

- Cost at 10 and 20 basis points per transaction.
- Placebo: the same before- and after-windows around the third Fridays of the eight non-update months, using the weights of the latest update before that month.
- Options-expiry control: the March windows (third Friday of March, also a quarterly options expiry) using the previous December's weights.
- Without MPC: the same test with MPC removed and the short side reweighted (dates with no short left are skipped).
- Random dates: each date's windows moved to random start days in the design period, same weights, 10,000 draws; share of draws whose average does at least as well.

## 6. What could break it

- Nine dates, and MPC is most of the short side on six of them; a result is close to a statement about MPC.
- The forced sale is modest (MPC about one day's volume) and announced two weeks ahead; MPC's own buybacks absorb about as much over the window.
- Quarter-end pauses in company buybacks fall in the after-window.
- Daily closes only; the trade happens in the closing auction.
- Cover-page share counts and Berkshire filings stand in for S&P's actual inputs; the float-review timing is from memory.
- The update day is also a quarterly options expiry.
- This forecast was revised after seeing which dates the first version missed, and its go/no-go bar was changed after the result.
