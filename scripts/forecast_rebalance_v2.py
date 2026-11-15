"""Forecast XLE's rebalance trades using only information public on the snapshot day (version 2).

Usage: python -I forecast_rebalance_v2.py <data_dir> <signals_out.csv>     write the forecast signals
       python -I forecast_rebalance_v2.py <data_dir> --check               also compare with actual trades (needs next quarter-end)
       python -I forecast_rebalance_v2.py --selftest

Cap rules, constants and the frozen old-rule reading are imported unchanged from forecast_rebalance.py (v1).
Only the step that builds each rebalance's inputs is replaced. Two differences from v1:

1. No look-ahead. v1 read XLE's holdings at the quarter-end AFTER the rebalance to decide which stocks
   get a forecast and to size companies that had just joined the S&P 500. Here:
   - a stock gets a forecast if XLE held it at the quarter-end before and it has a snapshot-day close;
   - a company that joined before the snapshot (listed in index_changes.csv) gets an index share count of
     (its latest 10-Q/10-K cover-page share count filed on or before the snapshot) x (the median, over the
     other members with cover-page data, of IVV holding / cover-page shares). An assumption: the joiner's
     float factor equals the members' median.
   The next quarter-end is read only in --check mode, to compare with actual trades.

2. Mergers from a table, not a special case. index_changes.csv lists each change effective on or before a
   snapshot: 'add' (S&P 500 joiner) or 'merge' (target -> acquirer at <ratio> acquirer shares per target
   share; ratio 0 for a cash deal), each with its SEC filing as source. A company held at the quarter-end
   before that has no snapshot close and no table entry stops the forecast for that rebalance (no signals),
   rather than guessing.
"""
import csv
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # -I drops the script folder
import forecast_rebalance as v1

TRADABLE, LARGE = v1.TRADABLE, v1.LARGE
FROZEN_READING = v1.FROZEN_READING


def load_changes(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="") as f:
        return [{**r, "ratio": float(r["ratio"]) if r["ratio"] else None} for r in csv.DictReader(f)]


def load_cover(paths):
    rows = []
    for p in paths:
        if os.path.exists(p):
            with open(p, newline="") as f:
                rows += list(csv.DictReader(f))
    return rows


def latest_cover(cover, ticker, on_or_before):
    hits = [r for r in cover if r["ticker"] == ticker and r["filed"] <= on_or_before]
    return float(max(hits, key=lambda r: r["filed"])["shares"]) if hits else None


def build_inputs(ev, xle_sh, ivv_sh, close, changes, cover):
    """Held shares and index share counts as known on the snapshot day. Returns (held, count, price, notes) or None."""
    ref, d0 = ev["snapshot_day"], ev["quarter_end_before"]
    price = {t: close[t][ref] for t in close if close[t].get(ref)}
    held = {t: xle_sh[t][d0] for t in xle_sh if xle_sh[t].get(d0)}
    count = {t: ivv_sh[t][d0] for t in ivv_sh if ivv_sh[t].get(d0)}
    count0 = dict(count)                         # unadjusted, for the IVV-holding fraction below
    notes = []
    live = [c for c in changes if d0 < c["effective"] <= ref]

    for c in live:
        if c["change"] == "merge" and c["ticker"] in held:
            tgt, acq, ratio = c["ticker"], c["acquirer"], c["ratio"]
            h, n = held.pop(tgt), count.pop(tgt, 0.0)
            if acq in held and ratio:
                held[acq] += ratio * h
                count[acq] += ratio * n
            notes.append(f"{tgt} merged into {acq or 'outside buyer'} at {ratio}")

    unpriced = sorted(t for t in held if t not in price)
    if unpriced:
        notes.append(f"STOP: held but no snapshot close and no table entry: {unpriced}")
        return None, None, None, notes

    joiners = [c["ticker"] for c in live if c["change"] == "add" and c["ticker"] not in held and c["ticker"] in price]
    if joiners:
        frac = [count0[t] / latest_cover(cover, t, ref) for t in count0 if latest_cover(cover, t, ref)]
        f = statistics.median(frac)
        for t in joiners:
            s = latest_cover(cover, t, ref)
            if s is None:
                notes.append(f"STOP: joiner {t} has no cover-page share count filed by {ref}")
                return None, None, None, notes
            count[t] = f * s
        notes.append(f"joined before snapshot: {joiners} (IVV fraction {f:.5f} from {len(frac)} members)")
    return held, count, price, notes


def forecast_event(ev, xle_sh, xle_w, ivv_sh, close, vol, changes, cover, rule_kwargs, check=False):
    held, count, price, notes = build_inputs(ev, xle_sh, ivv_sh, close, changes, cover)
    if held is None:
        return [], notes
    joiners = [t for t in count if t not in held]
    size = {t: count[t] * price[t] for t in count}
    natural = {t: 100 * v / sum(size.values()) for t, v in size.items()}
    target = v1.new_rule(natural) if ev["rule"] == "new" else v1.old_rule(natural, **rule_kwargs)

    value_old = sum(held[t] * price[t] for t in held)
    fund_value = value_old / (1 - sum(natural[t] for t in joiners) / 100)
    for t in joiners:                            # assume the fund already holds a joiner at its natural weight (as v1)
        held[t] = natural[t] / 100 * fund_value / price[t]

    if check:                                    # hindsight, for the forecast check only (as v1)
        d1 = ev["quarter_end_after"]
        now = {t: xle_sh[t][d1] for t in xle_sh if xle_sh[t].get(d1)}
        qe_price = {t: xle_w[t][d1] / 100 * xle_w["NETASSETS_USD_M"][d1] * 1e6 / now[t] for t in now}
        scale = sum(qe_price[t] * now[t] for t in now) / sum(qe_price[t] * held.get(t, 0.0) for t in now)

    rows = []
    for t in TRADABLE:
        if t not in held:
            continue
        predicted = target[t] / 100 * fund_value / price[t] - held[t]
        v = vol[t][ev["snapshot_day"]] * 1e6
        row = {"event": ev["rebalance_day"], "snapshot": ev["snapshot_day"], "ticker": t, "pred_days": predicted / v}
        if check:
            row["act_days"] = (now[t] - scale * held[t]) / v if t in now else None
        rows.append(row)
    return rows, notes


def main(data_dir, out):
    with open(f"{data_dir}/outside/calendar_design.csv", newline="") as f:
        events = list(csv.DictReader(f))
    xle_sh = v1.load(f"{data_dir}/sec/xle_quarter_end_shares.csv")
    xle_w = v1.load(f"{data_dir}/sec/xle_quarter_end_weights_pct.csv")
    ivv_sh = v1.load(f"{data_dir}/sec/ivv_energy_quarter_end_shares.csv")
    close = v1.load(f"{data_dir}/outside/snapshot_day_closes.csv")
    vol = v1.load(f"{data_dir}/outside/snapshot_day_volume_60d.csv")
    changes = load_changes(f"{data_dir}/outside/index_changes.csv")
    cover = load_cover([f"{data_dir}/sec/cover_page_shares.csv", f"{data_dir}/sec/cover_page_shares_joiners.csv"])
    check = out == "--check"

    rows_all = []
    for ev in events:
        rows, notes = forecast_event(ev, xle_sh, xle_w, ivv_sh, close, vol, changes, cover, FROZEN_READING, check)
        for n in notes:
            print(f"{ev['rebalance_day']}: {n}")
        rows_all += rows
    if check:
        both = [r for r in rows_all if r["act_days"] is not None]
        big_act = [r for r in both if abs(r["act_days"]) >= LARGE]
        hits = [r for r in big_act if abs(r["pred_days"]) >= LARGE and r["pred_days"] * r["act_days"] > 0]
        print(f"large actual trades {len(big_act)}, forecast right on {len(hits)}; correlation "
              f"{statistics.correlation([r['pred_days'] for r in both], [r['act_days'] for r in both]):.2f}")
        return
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["snapshot_day", "rebalance_day", "ticker", "forecast_days"])
        for r in rows_all:
            w.writerow([r["snapshot"], r["event"], r["ticker"], round(r["pred_days"], 4)])
    print(f"forecast signals written to {out} ({len(rows_all)} rows)")


def selftest():
    ev = {"snapshot_day": "2025-03-12", "rebalance_day": "2025-03-21", "quarter_end_before": "2024-12-31",
          "quarter_end_after": "2025-03-31", "rule": "new"}
    xle = {"AAA": {"2024-12-31": 100.0}, "BBB": {"2024-12-31": 50.0}, "CCC": {"2024-12-31": 10.0}}
    ivv = {"AAA": {"2024-12-31": 1000.0}, "BBB": {"2024-12-31": 500.0}, "CCC": {"2024-12-31": 100.0}}
    close = {"AAA": {"2025-03-12": 10.0}, "BBB": {"2025-03-12": 20.0}, "NEW": {"2025-03-12": 5.0}}
    cover = [{"ticker": "AAA", "filed": "2025-02-01", "shares": "100000"}, {"ticker": "BBB", "filed": "2025-02-01", "shares": "50000"},
             {"ticker": "NEW", "filed": "2025-02-20", "shares": "20000"}, {"ticker": "NEW", "filed": "2025-03-20", "shares": "99"}]
    # CCC unpriced and not in the table -> stop
    h, c, p, notes = build_inputs(ev, xle, ivv, close, [], cover)
    assert h is None and "STOP" in notes[-1]
    # CCC merged into AAA at 0.5; NEW joined: count = median(1000/100000, 500/50000) * 20000 = 200
    changes = [{"effective": "2025-01-15", "ticker": "CCC", "change": "merge", "acquirer": "AAA", "ratio": 0.5},
               {"effective": "2025-02-01", "ticker": "NEW", "change": "add", "acquirer": "", "ratio": None}]
    h, c, p, notes = build_inputs(ev, xle, ivv, close, changes, cover)
    assert h == {"AAA": 105.0, "BBB": 50.0} and c["AAA"] == 1050.0 and abs(c["NEW"] - 200.0) < 1e-9, (h, c)
    # a change dated after the snapshot is ignored
    late = [{**changes[0], "effective": "2025-03-13"}]
    assert build_inputs(ev, xle, ivv, close, late, cover)[0] is None
    print("selftest OK")


if __name__ == "__main__":
    selftest() if sys.argv[1] == "--selftest" else main(sys.argv[1], sys.argv[2])
