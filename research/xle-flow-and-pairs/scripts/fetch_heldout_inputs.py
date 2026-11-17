"""Build the HELD-OUT event calendar and fetch what the forecast needs on each snapshot day.

Held-out version of fetch_snapshot_inputs.py, for strategy variant 6 (hypothesis-sells-reversal.md).
Running the fetch OPENS THE HELD-OUT WINDOW, so it is gated twice: it needs the --open-heldout flag,
and it refuses to start unless this script, the rules file and the back-test script match their
frozen fingerprints in output/frozen_fingerprints.txt.

Usage (from scripts/):
  python -I fetch_heldout_inputs.py --selftest                      offline; no data read or fetched
  python -I fetch_heldout_inputs.py --calendar <out_dir>            writes the calendar only; no data read
  python -I fetch_heldout_inputs.py --check-sec <data_dir>          checks the hand-pulled SEC files are complete
  python -I fetch_heldout_inputs.py --open-heldout <data_dir> [<path to .env>]

<data_dir> is a folder laid out like data/ (e.g. ../data_heldout), so the frozen forecast_rebalance.py
can read it unchanged:
  sec/xle_quarter_end_shares.csv         XLE holdings, shares, from SEC N-PORT (pulled by hand in the browser,
  sec/xle_quarter_end_weights_pct.csv    the same way as attempts #3 and #5; weights file has a NETASSETS_USD_M row)
  sec/ivv_energy_quarter_end_shares.csv  IVV energy holdings, shares, from SEC N-PORT
  outside/calendar_design.csv            written here (the frozen code expects this file name)
  outside/snapshot_day_closes.csv        written here: unadjusted close of every member on each snapshot day
  outside/snapshot_day_volume_60d.csv    written here: median daily volume (million shares), 60 trading days to the snapshot
  outside/index_changes.csv              hand-filled: S&P 500 joiners and mergers effective before each snapshot, each
                                         with its source (S&P announcement or SEC 8-K) dated before that snapshot
  sec/cover_page_shares.csv              hand-filled from SEC companyconcept (dei:EntityCommonStockSharesOutstanding) for
                                         the members and any joiner, as in attempt #10

Signals come from forecast_rebalance_v2.py, which needs only the quarter-end BEFORE each rebalance; the
quarter-end after is optional and used only for the forecast check.

Only snapshot-day closes and trailing volume are kept. No returns are computed.
Members are every ticker XLE holds at any needed quarter-end (from the SEC file), not a fixed list.
Delisted tickers that Yahoo no longer serves are filled from Alpaca raw daily bars if a .env path is given
(keys are read from it and never printed).

Calendar rules (S&P U.S. Indices Methodology, Select Sector Indices; read 2026-11-15, November 2026 edition):
  rebalance day = third Friday of Mar/Jun/Sep/Dec; new capping rule for every held-out rebalance
  snapshot day  = second Friday through December 2024; the Wednesday before the second Friday from March 2025
  holiday       = the methodology only says the committee may move the date. Fixed in advance here: a scheduled
                  day that is not a trading day moves to the last trading day before it (affects 19 June 2026,
                  Juneteenth). Flagged in the output; S&P's actual announced date is not looked up.
"""
import csv
import datetime as dt
import hashlib
import json
import os
import statistics
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

HELDOUT_START, HELDOUT_END = dt.date(2024, 11, 1), dt.date(2026, 10, 30)
REBALANCE_MONTHS = [(2024, 12)] + [(y, m) for y in (2025, 2026) for m in (3, 6, 9, 12)]
WEDNESDAY_FROM = dt.date(2024, 12, 21)        # reference-date change effective date (methodology change history)
FETCH_FROM = dt.date(2024, 6, 1)              # far enough back for 60 trading days before the first snapshot
TRADABLE = ["XOM", "CVX", "COP", "EOG", "OXY", "SLB", "MPC", "PSX", "VLO"]
FROZEN = ("hypothesis-sells-reversal.md", "scripts/sells_reversal.py", "scripts/fetch_heldout_inputs.py",
          "scripts/forecast_rebalance_v2.py", "scripts/forecast_rebalance.py")


# ---------- calendar (no data) ----------

def nth_friday(year, month, n):
    first = dt.date(year, month, 1)
    return first + dt.timedelta(days=(4 - first.weekday()) % 7 + 7 * (n - 1))


def quarter_ends():
    return [dt.date(y, m, 30 if m in (6, 9) else 31) for y in range(2024, 2027) for m in (3, 6, 9, 12)]


def scheduled_events():
    """(snapshot, rebalance, quarter_end_before, quarter_end_after) as scheduled, before holiday moves."""
    out = []
    for y, m in REBALANCE_MONTHS:
        eff = nth_friday(y, m, 3)
        if not (HELDOUT_START <= eff <= HELDOUT_END):
            continue
        second = nth_friday(y, m, 2)
        ref = second - dt.timedelta(days=2) if eff > WEDNESDAY_FROM else second
        before = max(e for e in quarter_ends() if e < eff)
        after = min(e for e in quarter_ends() if e >= eff)
        out.append((ref, eff, before, after))
    return out


def move_to_trading_day(d, trading_days):
    """A scheduled day that is not a trading day moves to the last trading day before it."""
    while d not in trading_days:
        d -= dt.timedelta(days=1)
    return d


def write_calendar(events, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "calendar_design.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["snapshot_day", "rebalance_day", "rule", "quarter_end_before", "quarter_end_after"])
        for ref, eff, before, after in events:
            w.writerow([ref, eff, "new", before, after])


# ---------- SEC file check (no prices) ----------

def needed_quarter_ends():
    """Required: the quarter-end before each rebalance. Optional (forecast check only): the one after."""
    before = sorted({e[2] for e in scheduled_events()})
    after = sorted({e[3] for e in scheduled_events()} - set(before))
    return before, after


def check_sec(data_dir):
    """Report which needed quarter-end columns are present in the hand-pulled SEC files. Returns members."""
    before, after = needed_quarter_ends()
    need, optional = [str(d) for d in before], [str(d) for d in after]
    ok, members = True, set()
    for name in ("xle_quarter_end_shares.csv", "xle_quarter_end_weights_pct.csv", "ivv_energy_quarter_end_shares.csv"):
        path = os.path.join(data_dir, "sec", name)
        if not os.path.exists(path):
            print(f"  {name}: MISSING FILE")
            ok = False
            continue
        with open(path, newline="") as f:
            rows = list(csv.reader(f))
        have = set(rows[0][1:])
        missing = [d for d in need if d not in have]
        opt_missing = [d for d in optional if d not in have]
        print(f"  {name}: {len(rows) - 1} rows; required quarter-ends missing: {missing or 'none'}"
              + (f"; optional (check only) missing: {opt_missing}" if opt_missing else ""))
        ok &= not missing
        if name == "xle_quarter_end_shares.csv":
            cols = [i for i, d in enumerate(rows[0]) if d in need or d in optional]
            members = {r[0] for r in rows[1:] if any(r[i] for i in cols)}
        if name == "xle_quarter_end_weights_pct.csv" and not any(r[0] == "NETASSETS_USD_M" for r in rows[1:]):
            print("  xle_quarter_end_weights_pct.csv: no NETASSETS_USD_M row")
            ok = False
    changes = os.path.join(data_dir, "outside", "index_changes.csv")
    if os.path.exists(changes):
        with open(changes, newline="") as f:
            members |= {r["ticker"] for r in csv.DictReader(f)}
    else:
        print("  outside/index_changes.csv: MISSING FILE (write it with a header row even if empty)")
        ok = False
    if not os.path.exists(os.path.join(data_dir, "sec", "cover_page_shares.csv")):
        print("  sec/cover_page_shares.csv: MISSING FILE")
        ok = False
    print("Inputs complete." if ok else "Inputs NOT complete; see above.")
    return ok, sorted(members)


# ---------- fetch (opens the held-out window) ----------

def check_fingerprints():
    want = {}
    with open(os.path.join(ROOT, "output", "frozen_fingerprints.txt")) as f:
        for line in f:
            parts = line.split()
            if len(parts) == 2 and len(parts[0]) == 64:
                want[parts[1]] = parts[0]
    for rel in FROZEN:
        with open(os.path.join(ROOT, rel), "rb") as f:
            if want.get(rel) != hashlib.sha256(f.read()).hexdigest():
                sys.exit(f"STOP: {rel} does not match a frozen fingerprint; held-out fetch refused.")
    print("Fingerprints checked OK.")


def fetch_yahoo(ticker):
    p1 = int(dt.datetime(FETCH_FROM.year, FETCH_FROM.month, FETCH_FROM.day).timestamp())
    p2 = int(dt.datetime(HELDOUT_END.year, HELDOUT_END.month, HELDOUT_END.day, 23).timestamp())
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?period1={p1}&period2={p2}&interval=1d&events=split"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        res = json.load(r)["chart"]["result"][0]
    q = res["indicators"]["quote"][0]
    days = [dt.datetime.fromtimestamp(t, dt.timezone.utc).date() for t in res["timestamp"]]
    splits = list(res.get("events", {}).get("splits", {}).values())
    return days, q["close"], q["volume"], splits


def fetch_alpaca(ticker, env_path):
    from alpaca.data.enums import Adjustment, DataFeed
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame
    from dotenv import dotenv_values
    env = dotenv_values(env_path)
    client = StockHistoricalDataClient(env["APCA_API_KEY_ID"], env["APCA_API_SECRET_KEY"])
    req = StockBarsRequest(symbol_or_symbols=ticker, timeframe=TimeFrame.Day, adjustment=Adjustment.RAW, feed=DataFeed.SIP,
                           start=dt.datetime(FETCH_FROM.year, FETCH_FROM.month, FETCH_FROM.day),
                           end=dt.datetime(HELDOUT_END.year, HELDOUT_END.month, HELDOUT_END.day))
    bars = client.get_stock_bars(req).data.get(ticker, [])
    return [b.timestamp.date() for b in bars], [b.close for b in bars], [b.volume for b in bars], []


def snapshot_values(days, close, volume, refs, want_volume):
    idx = {d: i for i, d in enumerate(days)}
    closes = [round(close[idx[r]], 4) if r in idx and close[idx[r]] else "" for r in refs]
    vols = []
    if want_volume:
        for r in refs:
            if r not in idx:
                vols.append("")
                continue
            window = [v for v in volume[max(0, idx[r] - 59): idx[r] + 1] if v]
            vols.append(round(statistics.median(window) / 1e6, 3))
    return closes, vols


def open_heldout(data_dir, env_path=None):
    check_fingerprints()
    ok, members = check_sec(data_dir)
    if not ok:
        sys.exit("STOP: complete the SEC files first (see above).")

    # trading days from XLE's own series, so the price file is not read here
    xle_days = set(fetch_yahoo("XLE")[0])
    events = []
    for ref, eff, before, after in scheduled_events():
        ref2, eff2 = move_to_trading_day(ref, xle_days), move_to_trading_day(eff, xle_days)
        for label, a, b in (("snapshot", ref, ref2), ("rebalance", eff, eff2)):
            if a != b:
                print(f"HOLIDAY MOVE: {label} day {a} is not a trading day; using {b}")
        events.append((ref2, eff2, before, after))
    write_calendar(events, os.path.join(data_dir, "outside"))
    print(f"calendar: {len(events)} rebalances, {events[0][1]} to {events[-1][1]}")

    refs = [e[0] for e in events]
    closes, volumes = {}, {}
    for t in sorted(set(members) | set(TRADABLE)):
        try:
            days, close, volume, splits = fetch_yahoo(t)
            src = "Yahoo"
        except Exception as exc:
            if not env_path:
                print(f"{t}: Yahoo FAILED ({exc}); no .env given for Alpaca")
                continue
            days, close, volume, splits = fetch_alpaca(t, env_path)
            src = "Alpaca"
        if splits:
            print(f"{t}: splits in the data {splits}")
        c, v = snapshot_values(days, close, volume, refs, t in TRADABLE)
        closes[t] = c
        if t in TRADABLE:
            volumes[t] = v
        missing = [str(r) for r, x in zip(refs, c) if x == ""]
        print(f"{t}: {src}" + (f"  no price on {missing}" if missing else ""))
        time.sleep(0.5)

    for name, table in (("snapshot_day_closes.csv", closes), ("snapshot_day_volume_60d.csv", volumes)):
        with open(os.path.join(data_dir, "outside", name), "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["ticker"] + [str(r) for r in refs])
            for t, row in table.items():
                w.writerow([t] + row)
    print("Snapshot inputs written. Next: forecast_rebalance_v2.py <data_dir> <signals.csv>, then sells_reversal.py heldout.")


# ---------- self-test (offline) ----------

def selftest():
    ev = scheduled_events()
    got = [(str(a), str(b)) for a, b, _, _ in ev]
    want = [("2024-12-13", "2024-12-20"), ("2025-03-12", "2025-03-21"), ("2025-06-11", "2025-06-20"),
            ("2025-09-10", "2025-09-19"), ("2025-12-10", "2025-12-19"), ("2026-03-11", "2026-03-20"),
            ("2026-06-10", "2026-06-19"), ("2026-09-09", "2026-09-18")]
    assert got == want, got
    assert [(str(b), str(c)) for _, _, b, c in ev][0] == ("2024-09-30", "2024-12-31")
    assert [(str(b), str(c)) for _, _, b, c in ev][-1] == ("2026-06-30", "2026-09-30")
    # holiday move: a Friday holiday goes to Thursday
    tdays = {dt.date(2026, 6, 18), dt.date(2026, 6, 17)}
    assert move_to_trading_day(dt.date(2026, 6, 19), tdays) == dt.date(2026, 6, 18)
    # snapshot values: close on the day, median volume of the trailing 60 days
    days = [dt.date(2025, 1, 1) + dt.timedelta(days=k) for k in range(100)]
    close = [float(k) for k in range(100)]
    volume = [1e6 * (k % 3 + 1) for k in range(100)]
    c, v = snapshot_values(days, close, volume, [days[80], dt.date(2030, 1, 1)], True)
    assert c == [80.0, ""] and v[0] == statistics.median(volume[21:81]) / 1e6 and v[1] == ""
    before, after = needed_quarter_ends()
    assert [str(d) for d in after] == ["2026-09-30"]
    print("required quarter-ends:", ", ".join(str(d) for d in before), "| optional:", ", ".join(str(d) for d in after))
    print("selftest OK")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "--selftest":
        selftest()
    elif a[0] == "--calendar":
        write_calendar(scheduled_events(), a[1])
        print("scheduled calendar written (holiday moves are applied only in --open-heldout)")
    elif a[0] == "--check-sec":
        check_sec(a[1])
    elif a[0] == "--open-heldout":
        open_heldout(a[1], a[2] if len(a) > 2 else None)
    else:
        sys.exit(__doc__)
