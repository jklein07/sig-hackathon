"""Back-test of the frozen hypothesis C2b (hypothesis-c2.md) on the DESIGN period only.

Usage: python -I c2_backtest_design.py <prices.csv> <c2b_signals.csv>

Rows after DESIGN_END are never read. Every number that defines the strategy is a constant below and
matches hypothesis-c2.md; the declared checks vary one thing at a time.
"""
import csv
import datetime as dt
import random
import statistics
import sys

DESIGN_END = dt.date(2024, 10, 31)
COST_BPS = 5                 # per transaction; four transactions per leg
MIN_RIGHT, MIN_AVG_COST_MULT = 8, 2
DRAWS, SEED = 10_000, 20261113


def load_prices(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    names = rows[0][1:]
    days, px = [], {n: [] for n in names}
    for r in rows[1:]:
        if not r or not r[0]:
            continue
        d = dt.datetime.strptime(r[0], "%m/%d/%Y").date()
        if d > DESIGN_END:
            break
        days.append(d)
        for n, v in zip(names, r[1:]):
            px[n].append(float(v))
    assert days[-1] <= DESIGN_END
    return days, px


def load_signals(path):
    ev = {}
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            u = dt.date.fromisoformat(r["update_day"])
            e = ev.setdefault(u, {"update": u, "n": int(r["n_before"]), "w": {}})
            if float(r["weight"]) != 0:
                e["w"][r["ticker"]] = float(r["weight"])
    return {u: e for u, e in ev.items() if e["w"]}


def spread(px, w, i0, i1):
    """Long-side minus short-side return, each side's weights scaled to sum to 1."""
    lw = {t: x for t, x in w.items() if x > 0}
    sw = {t: -x for t, x in w.items() if x < 0}
    if not lw or not sw:
        return None
    ret = lambda t: px[t][i1] / px[t][i0] - 1
    return (sum(x * ret(t) for t, x in lw.items()) / sum(lw.values())
            - sum(x * ret(t) for t, x in sw.items()) / sum(sw.values()))


def legs(px, w, iu, n):
    """Signed so that positive = prediction right."""
    b = spread(px, w, iu - n, iu)
    a = spread(px, w, iu, iu + n) if iu + n < len(px["MPC"]) else None
    return (b, -a if a is not None else None)


def third_friday(y, m):
    d = dt.date(y, m, 1)
    d += dt.timedelta(days=(4 - d.weekday()) % 7)
    return d + dt.timedelta(days=14)


def verdict(vals, cost_bps):
    cost = 4 * cost_bps / 1e4
    right, avg = sum(v > 0 for v in vals), statistics.mean(vals)
    ok = right >= MIN_RIGHT and avg >= MIN_AVG_COST_MULT * cost and len(vals) == 9
    return right, avg, cost, ("SUPPORTED" if ok else "NOT SUPPORTED")


def run_windows(px, idx, events, weights_fn, days_list):
    out = []
    for d, n in days_list:
        if d not in idx:
            continue
        w = weights_fn(d)
        if not w:
            continue
        b, a = legs(px, w, idx[d], n)
        if b is not None and a is not None:
            out.append((d, b, a))
    return out


def fmt(rows):
    if not rows:
        return "no windows"
    b = [r[1] for r in rows]
    a = [r[2] for r in rows]
    return (f"{len(rows)} windows; before right sign {sum(x > 0 for x in b)}/{len(b)}, average {statistics.mean(b):+.2%}; "
            f"after right sign {sum(x > 0 for x in a)}/{len(a)}, average {statistics.mean(a):+.2%}")


def main(prices_path, signals_path):
    days, px = load_prices(prices_path)
    idx = {d: i for i, d in enumerate(days)}
    events = load_signals(signals_path)
    print(f"BACK-TEST C2b, DESIGN PERIOD ONLY ({days[0]} to {days[-1]}), rules as frozen in hypothesis-c2.md")
    print("Spread = long side minus short side; signed so positive = prediction right. Before costs unless stated.\n")
    print(f"{'update':<12}{'days':>5}{'before':>9}{'after':>9}   short side (weight)")
    res = []
    for u, e in sorted(events.items()):
        b, a = legs(px, e["w"], idx[u], e["n"])
        res.append((u, b, a))
        shorts = ", ".join(f"{t} {-x:.0%}" for t, x in sorted(e["w"].items(), key=lambda kv: kv[1]) if x < 0)
        print(f"{u!s:<12}{e['n']:>5}{b:>+9.2%}{a:>+9.2%}   {shorts}")

    rng = random.Random(SEED)
    print()
    for k, name in ((1, "BEFORE-WINDOW"), (2, "AFTER-WINDOW")):
        vals = [r[k] for r in res]
        right, avg, cost, v = verdict(vals, COST_BPS)
        better = 0
        for _ in range(DRAWS):
            tot = 0.0
            for u, e in sorted(events.items()):
                n = e["n"]
                s = rng.randrange(0, len(days) - n)
                sp = spread(px, e["w"], s, s + n)
                tot += sp if k == 1 else -sp
            better += tot / len(events) >= avg
        print(f"{name}: right sign on {right} of {len(vals)}; average {avg:+.2%} (median {statistics.median(vals):+.2%}); "
              f"after {cost:.2%} cost {avg - cost:+.2%}; return on capital per event after costs {(avg - cost) / 2:+.2%}, "
              f"summed over events {sum((x - cost) / 2 for x in vals):+.2%}")
        print(f"  frozen test (at least {MIN_RIGHT} of 9 right, average at least {MIN_AVG_COST_MULT * cost:.2%}): {v}")
        print(f"  random dates: chance alone did as well in {better / DRAWS:.1%} of {DRAWS:,} draws")

    print("\nDECLARED CHECKS (not results)")
    for c in (10, 20):
        parts = []
        for k, name in ((1, "before"), (2, "after")):
            vals = [r[k] for r in res]
            right, avg, cost, v = verdict(vals, c)
            parts.append(f"{name}: average after cost {avg - cost:+.2%} ({v})")
        print(f"  cost {c} bps per transaction: " + "; ".join(parts))

    ups = sorted(events)
    latest_w = lambda d: next((events[u]["w"] for u in reversed(ups) if u < d), None)
    placebo_days = []
    for y in range(2021, 2025):
        for m in range(1, 13):
            if m in (3, 6, 9, 12):
                continue
            tf = third_friday(y, m)
            if tf in idx and idx[tf] >= 10 and tf <= DESIGN_END:
                n = idx[tf] - max(i for i, d in enumerate(days) if d <= tf - dt.timedelta(days=14))
                placebo_days.append((tf, n))
    print("  placebo, non-update third Fridays, latest update's weights: " + fmt(run_windows(px, idx, events, latest_w, placebo_days)))

    march = []
    for y in (2022, 2023, 2024):
        tf = third_friday(y, 3)
        n = idx[tf] - max(i for i, d in enumerate(days) if d <= tf - dt.timedelta(days=14))
        march.append((tf, n))
    dec_w = lambda d: next((events[u]["w"] for u in reversed(ups) if u < d and u.month == 12), None)
    print("  options-expiry control, March windows with December weights: " + fmt(run_windows(px, idx, events, dec_w, march)))

    nompc = []
    for u, e in sorted(events.items()):
        w = {t: x for t, x in e["w"].items() if t != "MPC"}
        b, a = legs(px, w, idx[u], e["n"])
        if b is not None:
            nompc.append((u, b, a))
    print("  without MPC (short side reweighted): " + fmt(nompc))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
