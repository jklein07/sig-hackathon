"""C2 (strategy variant 2): forecast which stocks S&P 500 index funds must sell at each quarterly
share update, from SEC cover-page share counts, and check the forecast against IVV's actual holdings.

Usage: python -I c2_forecast_shrink.py <data_dir> <output_dir> [--float]
       --float (attempt #11, "C2b"): also remove Berkshire Hathaway's disclosed stakes
       (data_dir/sec/berkshire_stakes.csv) from index shares at September updates only; outputs go to
       c2b_signals.csv and c2b_forecast_check.txt
       (reads data_dir/prices.csv DATE COLUMN ONLY, data_dir/sec/cover_page_shares.csv,
        data_dir/sec/ivv_energy_quarter_end_shares.csv; writes c2_signals.csv and c2_forecast_check.txt)

No prices or returns are read or computed here.

Rules (S&P Equity Indices Policies & Practices, "Rebalancing Guidelines - Share/IWF Reference Date &
Freeze Period": printed p.16 in the August 2021, April 2023 and April 2024 editions, same wording):
  - update day      = third Friday of Mar/Jun/Sep/Dec, after the close
  - reference date  = after the close five weeks before the third Friday; filings dated on or before it count
  - pro-forma file  = after the close on the first Friday, two weeks before the update (float-adjusted indices)

Shrink of a stock at an update = 1 - (shares on the latest filing filed on or before this reference date)
                                    / (shares on the latest filing filed on or before the previous reference date)
Dropped: no new filing; share count rose (catches merger share issues: XOM-Pioneer, CVX-PDC, PSX-PSXP,
OXY-CrownRock); tender offer in the interval (MPC's only one, May-June 2021, is before every interval).
Weight = (mean shrink of stocks still in - stock's shrink), scaled so longs sum to +0.5 and shorts to -0.5.
A date needs at least one long and one short.

GO/NO-GO, fixed before this script was first run (2026-11-13):
  IVV-implied index change for a stock over the quarter containing the update =
      (IVV shares at quarter-end / previous quarter-end) / median of that ratio over all 23 names - 1
  PASS only if BOTH:
    (a) MPC is the largest shrinker under both forecast and IVV on at least 8 of the 9 usable dates, and
    (b) sign of (shrink - mean shrink of stocks in) agrees between forecast and IVV on >= 80% of
        non-dropped stock-dates.
"""
import csv
import datetime as dt
import os
import statistics
import sys

DESIGN_START, DESIGN_END = dt.date(2021, 11, 1), dt.date(2024, 10, 31)
STOCKS = ["XOM", "CVX", "COP", "EOG", "OXY", "SLB", "MPC", "PSX", "VLO"]
TENDERS = {}   # ticker -> list of (start, end) tender periods; none fall inside the design intervals


def third_friday(y, m):
    d = dt.date(y, m, 1)
    d += dt.timedelta(days=(4 - d.weekday()) % 7)
    return d + dt.timedelta(days=14)


def trading_days(prices_path):
    with open(prices_path, newline="", encoding="utf-8-sig") as f:
        r = csv.reader(f)
        next(r)
        days = []
        for row in r:
            if not row or not row[0]:
                continue
            d = dt.datetime.strptime(row[0], "%m/%d/%Y").date()
            if d > DESIGN_END:
                break
            days.append(d)          # only the date column is touched
    assert days[-1] <= DESIGN_END
    return days


def on_or_before(days, d):
    return max(i for i, x in enumerate(days) if x <= d)


def calendar(days):
    out = []
    for y in range(2021, 2025):
        for m in (3, 6, 9, 12):
            upd = third_friday(y, m)
            if not (DESIGN_START < upd <= DESIGN_END):
                continue
            pm = m - 3 if m > 3 else 12
            py = y if m > 3 else y - 1
            iu, ie = on_or_before(days, upd), on_or_before(days, upd - dt.timedelta(days=14))
            n = iu - ie
            assert days[iu] == upd
            out.append({"update": upd, "ref": upd - dt.timedelta(days=35),
                        "prev_ref": third_friday(py, pm) - dt.timedelta(days=35),
                        "entry": days[ie], "n_before": n,
                        "after_end": days[iu + n] if iu + n < len(days) else None})
    return out


def load_filings(path):
    f = {}
    with open(path, newline="") as fh:
        for r in csv.DictReader(fh):
            f.setdefault(r["ticker"], []).append({"filed": dt.date.fromisoformat(r["filed"]), "as_of": r["as_of"],
                                                  "shares": int(r["shares"]), "accn": r["accn"]})
    return f


def latest(filings, d):
    c = [x for x in filings if x["filed"] <= d]
    return max(c, key=lambda x: (x["filed"], x["as_of"])) if c else None


def load_stakes(path):
    st = {}
    with open(path, newline="") as fh:
        for r in csv.DictReader(fh):
            st.setdefault(r["ticker"], []).append((dt.date.fromisoformat(r["filed"]), r["holding_date"], int(r["shares"])))
    return st


def stake_at(stakes, t, d):
    """Berkshire's holding in the latest filing (13F or Form 4) filed on or before d."""
    c = [x for x in stakes.get(t, []) if x[0] <= d]
    return max(c, key=lambda x: (x[0], x[1]))[2] if c else 0


def iwf_ref(ref):
    """Reference date of the latest September update on or before this reference date."""
    y = ref.year if ref >= third_friday(ref.year, 9) - dt.timedelta(days=35) else ref.year - 1
    return third_friday(y, 9) - dt.timedelta(days=35)


def forecast(cal, filings, stakes=None):
    rows = []
    for e in cal:
        recs = []
        for t in STOCKS:
            new, old = latest(filings[t], e["ref"]), latest(filings[t], e["prev_ref"])
            s_new = stake_at(stakes, t, iwf_ref(e["ref"])) if stakes else 0
            s_old = stake_at(stakes, t, iwf_ref(e["prev_ref"])) if stakes else 0
            shrink = 1 - (new["shares"] - s_new) / (old["shares"] - s_old)
            reason = ""
            if new["accn"] == old["accn"] and s_new == s_old:
                reason = "no new filing"
            elif new["shares"] > old["shares"]:
                reason = "share count rose"
            elif any(old["filed"] < b and a <= e["ref"] for a, b in TENDERS.get(t, [])):
                reason = "tender offer"
            recs.append({"update": e["update"], "ticker": t, "old_as_of": old["as_of"], "old_filed": old["filed"],
                         "new_as_of": new["as_of"], "new_filed": new["filed"], "shrink": shrink,
                         "dropped": reason, "weight": 0.0})
        live = [r for r in recs if not r["dropped"]]
        if live:
            avg = statistics.mean(r["shrink"] for r in live)
            pos = sum(avg - r["shrink"] for r in live if avg - r["shrink"] > 0)
            neg = sum(r["shrink"] - avg for r in live if avg - r["shrink"] < 0)
            if pos > 0 and neg > 0:
                for r in live:
                    s = avg - r["shrink"]
                    r["weight"] = 0.5 * s / pos if s > 0 else -0.5 * (-s) / neg
        rows += recs
    return rows


def ivv_change(path):
    with open(path, newline="") as f:
        r = list(csv.reader(f))
    qe = [dt.date.fromisoformat(x) for x in r[0][1:]]
    sh = {row[0]: [float(v) if v else 0.0 for v in row[1:]] for row in r[1:]}
    out = {}
    for k in range(1, len(qe)):
        ratios = {t: v[k] / v[k - 1] for t, v in sh.items() if v[k - 1] > 0 and v[k] > 0}
        med = statistics.median(ratios.values())
        out[qe[k]] = {t: 1 - x / med for t, x in ratios.items()}      # positive = shrank vs median
    return out


def quarter_end(d):
    return dt.date(d.year, 12, 31) if d.month == 12 else dt.date(d.year, d.month + 1, 1) - dt.timedelta(days=1)


def main(data_dir, out_dir, use_float=False):
    days = trading_days(os.path.join(data_dir, "prices.csv"))
    cal = calendar(days)
    stakes = load_stakes(os.path.join(data_dir, "sec", "berkshire_stakes.csv")) if use_float else None
    tag = "c2b" if use_float else "c2"
    rows = forecast(cal, load_filings(os.path.join(data_dir, "sec", "cover_page_shares.csv")), stakes)
    ivv = ivv_change(os.path.join(data_dir, "sec", "ivv_energy_quarter_end_shares.csv"))
    calmap = {e["update"]: e for e in cal}

    with open(os.path.join(out_dir, f"{tag}_signals.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["update_day", "entry_day", "n_before", "after_end_day", "ticker", "old_as_of", "old_filed",
                    "new_as_of", "new_filed", "shrink_pct", "dropped", "weight"])
        for r in rows:
            e = calmap[r["update"]]
            w.writerow([r["update"], e["entry"], e["n_before"], e["after_end"], r["ticker"], r["old_as_of"],
                        r["old_filed"], r["new_as_of"], r["new_filed"], f"{100 * r['shrink']:.3f}", r["dropped"],
                        f"{r['weight']:.4f}"])

    lines = [f"{tag.upper()} FORECAST CHECK (no prices or returns used)", "",
             f"{'update':<12}{'entry':<12}{'days':>5}  {'stock':<5}{'fcst shrink':>12}{'IVV shrink':>12}  {'weight':>7}  dropped"]
    usable, mpc_top, agree, total = [], 0, 0, 0
    for e in cal:
        recs = [r for r in rows if r["update"] == e["update"]]
        q = ivv.get(quarter_end(e["update"]), {})
        for r in recs:
            lines.append(f"{e['update']!s:<12}{e['entry']!s:<12}{e['n_before']:>5}  {r['ticker']:<5}"
                         f"{100 * r['shrink']:>11.2f}%{100 * q.get(r['ticker'], float('nan')):>11.2f}%  "
                         f"{r['weight']:>+7.3f}  {r['dropped']}")
        live = [r for r in recs if not r["dropped"] and r["weight"] != 0]
        if not live:
            lines.append("  -> no trade (fewer than one long and one short)")
            continue
        usable.append(e["update"])
        fa = statistics.mean(r["shrink"] for r in live)
        ia = statistics.mean(q[r["ticker"]] for r in live)
        for r in live:
            total += 1
            agree += (r["shrink"] > fa) == (q[r["ticker"]] > ia)
        top_f = max(live, key=lambda r: r["shrink"])["ticker"]
        top_i = max(live, key=lambda r: q[r["ticker"]])["ticker"]
        mpc_top += top_f == "MPC" and top_i == "MPC"
        mpc_w = next((r["weight"] for r in live if r["ticker"] == "MPC"), 0.0)
        lines.append(f"  -> largest shrinker: forecast {top_f}, IVV {top_i}; MPC share of short side "
                     f"{-mpc_w / 0.5:.0%}")
        lines.append("")
    a = mpc_top >= 8 and len(usable) == 9
    b = total and agree / total >= 0.80
    lines += ["", f"Usable dates: {len(usable)} ({', '.join(map(str, usable))})",
              f"(a) MPC largest shrinker under both sources on {mpc_top} of {len(usable)} dates (need >= 8 of 9): "
              f"{'PASS' if a else 'FAIL'}",
              f"(b) sign agreement on {agree} of {total} stock-dates = {agree / total:.0%} (need >= 80%): "
              f"{'PASS' if b else 'FAIL'}",
              f"GO/NO-GO: {'GO' if a and b else 'NO-GO'}"]
    with open(os.path.join(out_dir, f"{tag}_forecast_check.txt"), "w") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], "--float" in sys.argv[3:])
