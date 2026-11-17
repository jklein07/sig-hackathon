"""Fill snapshot-day closes for tickers Yahoo no longer serves (delisted after takeovers).

Usage: python -I fill_missing_closes_alpaca.py <path to .env> <snapshot_day_closes.csv> TICKER [TICKER ...]

Uses Alpaca daily bars (raw, unadjusted, SIP feed). The API keys are read from the
.env file and are never printed. Only the snapshot-day closes are kept.
"""
import csv
import datetime as dt
import sys

from alpaca.data.enums import Adjustment, DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from dotenv import dotenv_values


def main(env_path, closes_path, tickers):
    env = dotenv_values(env_path)
    client = StockHistoricalDataClient(env["APCA_API_KEY_ID"], env["APCA_API_SECRET_KEY"])

    with open(closes_path, newline="") as f:
        rows = list(csv.reader(f))
    header = rows[0]
    refs = [dt.date.fromisoformat(d) for d in header[1:]]
    have = {r[0] for r in rows[1:]}

    for t in tickers:
        if t in have:
            print(f"{t}: already present, skipped")
            continue
        request = StockBarsRequest(symbol_or_symbols=t, timeframe=TimeFrame.Day, adjustment=Adjustment.RAW,
                                   feed=DataFeed.SIP, start=dt.datetime(2021, 11, 1), end=dt.datetime(2024, 10, 31))
        bars = client.get_stock_bars(request).data.get(t, [])
        by_day = {b.timestamp.date(): b.close for b in bars}
        row = [round(by_day[r], 4) if r in by_day else "" for r in refs]
        first, last = (min(by_day), max(by_day)) if by_day else (None, None)
        missing = [str(r) for r, c in zip(refs, row) if c == ""]
        print(f"{t}: {len(bars)} bars, {first} to {last}" + (f"  no price on {missing}" if missing else ""))
        rows.append([t] + row)

    with open(closes_path, "w", newline="") as f:
        csv.writer(f).writerows(rows)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3:])
