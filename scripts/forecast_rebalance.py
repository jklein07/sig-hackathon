"""Forecast XLE's rebalance trades from snapshot-day information, and check the forecast.

Usage: python -I forecast_rebalance.py <data_dir>      (expects data_dir/sec and data_dir/outside)
       python -I forecast_rebalance.py --selftest

For each rebalance in the design period:
  1. natural weight  = share count (S&P 500 fund holdings at the previous quarter-end) x snapshot-day price
  2. target weight   = natural weights passed through the cap rule in force
  3. current weight  = XLE's holdings at the previous quarter-end x snapshot-day price
  4. predicted trade = target minus current, in shares and in days of normal volume
  5. actual trade    = change in XLE's holdings to the next quarter-end, beyond the fund's overall scaling

Step 5 is hindsight and is used only to check the forecast. No returns are computed anywhere.

The old rule (before 20 Sep 2024) is ambiguous on two points, so four readings are run:
  order = "cumulative": walk the big companies from largest down; the one that pushes the running
                        total over 50% is cut to 4.5%
  order = "smallest":   the smallest big company is cut to 4.5% first
  bound = None / 4.5:   whether companies receiving the removed weight are held at 4.5%
"""
import csv
import statistics
import sys

SINGLE_TRIGGER, SINGLE_CAP = 24.0, 23.0
BIG, GROUP_LIMIT, GROUP_TARGET, SMALL_CAP = 4.8, 50.0, 45.0, 4.5
PXD_TO_XOM = 2.3234          # Exxon shares per Pioneer share in the May 2024 takeover (from memory; to confirm)
TRADABLE = ["XOM", "CVX", "COP", "EOG", "OXY", "SLB", "MPC", "PSX", "VLO"]
LARGE = 0.5                  # days of normal volume


def spread(w, excess, recipients, cap=None):
    """Hand `excess` to `recipients` in proportion to their weight, optionally holding each at `cap`."""
    active = [t for t in recipients if cap is None or w[t] < cap]
    while excess > 1e-12 and active:
        total = sum(w[t] for t in active)
        over = [t for t in active if cap is not None and w[t] + excess * w[t] / total > cap]
        if not over:
            for t in active:
                w[t] += excess * w[t] / total
            return 0.0
        for t in over:
            excess -= cap - w[t]
            w[t] = cap
            active.remove(t)
    return excess


def single_cap(w):
    """If any company is above 24%, hold it at 23%. Returns the capped tickers and the removed weight."""
    capped, removed = set(), 0.0
    for t in [t for t, v in w.items() if v > SINGLE_TRIGGER]:
        removed += w[t] - SINGLE_CAP
        w[t] = SINGLE_CAP
        capped.add(t)
    return capped, removed


def old_rule(natural, order="cumulative", bound=None):
    w = dict(natural)
    capped, removed = single_cap(w)
    while removed > 1e-12:                       # removed weight goes to every uncapped company
        spread(w, removed, [t for t in w if t not in capped])
        removed = 0.0
        for t in [t for t in w if t not in capped and w[t] > SINGLE_CAP]:
            removed += w[t] - SINGLE_CAP
            w[t] = SINGLE_CAP
            capped.add(t)
    cut = set()
    for _ in range(len(w)):
        group = sorted((t for t in w if w[t] > BIG and t not in cut), key=lambda t: -w[t])
        if sum(w[t] for t in group) <= GROUP_LIMIT:
            break
        if order == "smallest":
            victim = group[-1]
        else:
            running = 0.0
            for victim in group:
                running += w[victim]
                if running > GROUP_LIMIT:
                    break
        excess = w[victim] - SMALL_CAP
        w[victim] = SMALL_CAP
        cut.add(victim)
        spread(w, excess, [t for t in w if t not in group and t not in cut], bound)
    return w


def new_rule(natural):
    w = dict(natural)
    single_cap(w)
    group = [t for t in w if w[t] > BIG]
    total = sum(w[t] for t in group)
    if total > GROUP_LIMIT:
        for t in group:
            w[t] = max(GROUP_TARGET * w[t] / total, SMALL_CAP)
    small = [t for t in w if natural[t] < BIG]
    for t in small:
        w[t] = min(w[t], SMALL_CAP)
    spread(w, 100.0 - sum(w.values()), small, SMALL_CAP)
    return w


def selftest():
    toy = {"A": 26.0, "B": 18.0, "C": 8.0, "D": 5.0, **{f"s{i}": 2.15 for i in range(20)}}
    w = new_rule(toy)
    assert abs(w["A"] - 45 * 23 / 54) < 1e-9 and abs(w["B"] - 15.0) < 1e-9 and abs(w["C"] - 45 * 8 / 54) < 1e-9
    big_total = 45 * 23 / 54 + 15.0 + 45 * 8 / 54 + 4.5       # D is floored at 4.5, so the group ends just above 45
    assert w["D"] == 4.5 and abs(sum(w.values()) - 100) < 1e-9 and abs(w["s0"] - (100 - big_total) / 20) < 1e-9
    toy = {"X": 26.0, "V": 19.0, "C": 9.0, "E": 4.0, **{f"s{i}": 2.0 for i in range(21)}}
    w = old_rule(toy)
    assert w["X"] == 23.0 and abs(w["V"] - 19 * 77 / 74) < 1e-9 and w["C"] == 4.5 and abs(sum(w.values()) - 100) < 1e-9
    assert abs(w["E"] - 4 * 77 / 74 * (1 + (9 * 77 / 74 - 4.5) / (4 * 77 / 74 + 42 * 77 / 74))) < 1e-9
    w = old_rule(toy, order="smallest", bound=4.5)
    assert w["C"] == 4.5 and max(w[f"s{i}"] for i in range(21)) <= 4.5 and abs(sum(w.values()) - 100) < 1e-9
    print("selftest OK")


def load(path):
    with open(path, newline="") as f:
        rows = list(csv.reader(f))
    dates = rows[0][1:]
    return {r[0]: {d: (float(v) if v else None) for d, v in zip(dates, r[1:])} for r in rows[1:]}


def forecast_event(ev, xle_sh, xle_w, ivv_sh, close, vol, rule_kwargs):
    ref, d0, d1 = ev["snapshot_day"], ev["quarter_end_before"], ev["quarter_end_after"]
    price = {t: close[t][ref] for t in close if close[t].get(ref)}
    held = {t: xle_sh[t][d0] for t in xle_sh if xle_sh[t][d0]}
    count = {t: ivv_sh[t][d0] for t in ivv_sh if ivv_sh[t][d0]}
    notes = []
    if "PXD" in held and "PXD" not in price:     # Pioneer became Exxon shares before this snapshot
        held["XOM"] += PXD_TO_XOM * held.pop("PXD")
        count["XOM"] += PXD_TO_XOM * count.pop("PXD")
        notes.append("PXD converted into XOM")
    joiners = [t for t in xle_sh if not xle_sh[t][d0] and xle_sh[t][d1] and t in price]
    if joiners:                                  # joined the S&P 500 before the snapshot; share count taken from the next filing
        growth = statistics.median(ivv_sh[t][d1] / ivv_sh[t][d0] for t in count)
        for t in joiners:
            count[t] = ivv_sh[t][d1] / growth
        notes.append(f"joined before snapshot: {joiners}")

    size = {t: count[t] * price[t] for t in count}
    natural = {t: 100 * v / sum(size.values()) for t, v in size.items()}
    target = new_rule(natural) if ev["rule"] == "new" else old_rule(natural, **rule_kwargs)

    value_old = sum(held[t] * price[t] for t in held)
    join_share = sum(natural[t] for t in joiners) / 100
    fund_value = value_old / (1 - join_share)
    for t in joiners:                            # assume the fund already holds a joiner at its natural weight
        held[t] = natural[t] / 100 * fund_value / price[t]
    current = {t: 100 * held[t] * price[t] / fund_value for t in held}

    now = {t: xle_sh[t][d1] for t in xle_sh if xle_sh[t][d1]}
    qe_price = {t: xle_w[t][d1] / 100 * xle_w["NETASSETS_USD_M"][d1] * 1e6 / now[t] for t in now}
    scale = sum(qe_price[t] * now[t] for t in now) / sum(qe_price[t] * held.get(t, 0.0) for t in now)

    rows = []
    for t in TRADABLE:
        if t not in held or t not in now:
            continue
        predicted = target[t] / 100 * fund_value / price[t] - held[t]
        actual = now[t] - scale * held[t]
        v = vol[t][ref] * 1e6
        rows.append({"event": ev["rebalance_day"], "snapshot": ref, "ticker": t, "natural": natural[t], "current": current[t],
                     "target": target[t], "pred_days": predicted / v, "act_days": actual / v})
    return rows, notes, natural, target


FROZEN_READING = dict(order="smallest", bound=4.5)   # the old-rule reading fixed in hypothesis.md


def main(data_dir, signals_path=None):
    with open(f"{data_dir}/outside/calendar_design.csv", newline="") as f:
        events = list(csv.DictReader(f))
    xle_sh = load(f"{data_dir}/sec/xle_quarter_end_shares.csv")
    xle_w = load(f"{data_dir}/sec/xle_quarter_end_weights_pct.csv")
    ivv_sh = load(f"{data_dir}/sec/ivv_energy_quarter_end_shares.csv")
    close = load(f"{data_dir}/outside/snapshot_day_closes.csv")
    vol = load(f"{data_dir}/outside/snapshot_day_volume_60d.csv")

    if signals_path:      # write the forecast only (no actual trades) for the back-test to read
        with open(signals_path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["snapshot_day", "rebalance_day", "ticker", "forecast_days"])
            for ev in events:
                for r in forecast_event(ev, xle_sh, xle_w, ivv_sh, close, vol, FROZEN_READING)[0]:
                    w.writerow([r["snapshot"], r["event"], r["ticker"], round(r["pred_days"], 4)])
        print(f"forecast signals written to {signals_path}")
        return

    variants = [dict(order=o, bound=b) for o in ("cumulative", "smallest") for b in (None, 4.5)]
    print("Forecast check: predicted against actual trades, in days of normal volume")
    print(f"'large' means at least {LARGE} days. {len(events)} rebalances x {len(TRADABLE)} tradable stocks.\n")
    for kw in variants:
        rows = []
        for ev in events:
            r, notes, _, _ = forecast_event(ev, xle_sh, xle_w, ivv_sh, close, vol, kw)
            rows += r
        big_act = [r for r in rows if abs(r["act_days"]) >= LARGE]
        big_pred = [r for r in rows if abs(r["pred_days"]) >= LARGE]
        hits = [r for r in big_act if abs(r["pred_days"]) >= LARGE and r["pred_days"] * r["act_days"] > 0]
        false_alarms = [r for r in big_pred if abs(r["act_days"]) < LARGE or r["pred_days"] * r["act_days"] < 0]
        p, a = [r["pred_days"] for r in rows], [r["act_days"] for r in rows]
        same_sign = sum(1 for x, y in zip(p, a) if x * y > 0) / len(rows)
        print(f"old-rule reading {kw}: large actual trades {len(big_act)}, forecast right on {len(hits)}, "
              f"missed {len(big_act) - len(hits)}, false alarms {len(false_alarms)}, "
              f"correlation {statistics.correlation(p, a):.2f}, same direction on {same_sign:.0%} of all {len(rows)} pairs")
        print(f"  {'rebalance':<12}{'stock':<6}{'natural':>8}{'current':>9}{'target':>8}{'predicted':>11}{'actual':>8}")
        for r in sorted(big_act + [x for x in false_alarms if x not in big_act], key=lambda r: (r["event"], r["ticker"])):
            tag = "hit" if r in hits else ("MISS" if r in big_act else "FALSE ALARM")
            print(f"  {r['event']:<12}{r['ticker']:<6}{r['natural']:>7.1f}%{r['current']:>8.1f}%{r['target']:>7.1f}%"
                  f"{r['pred_days']:>+10.1f}d{r['act_days']:>+7.1f}d  {tag}")
        print()


if __name__ == "__main__":
    selftest() if sys.argv[1] == "--selftest" else main(*sys.argv[1:3])
