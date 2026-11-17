"""Feasibility check: which quarters did XLE make an index-driven trade, and how big?

Usage: python -I xle_rebalance_check.py <shares.csv> <weights_pct.csv> [median_volume.csv]

Input is XLE's quarter-end holdings from its SEC N-PORT filings (design period
only). No returns are computed.

Method. When investors add or withdraw money, the fund scales every holding by
the same factor. A holding whose share count grows clearly more or less than
that factor was bought or sold relative to the rest: an index weight change (a
trim, a release from a trim, or a change in the company's own share count such
as a buyback or a stock-funded merger). The comparison is quarter-end to
quarter-end, so it shows that a trade happened in the quarter, not on which day.
"""
import csv
import statistics
import sys

FLAG = 0.05  # flag a holding whose growth differs from the common factor by over 5%
CHECKSUM = {  # sum of shares per date as reported by the extraction step
    "2021-09-30": 516097956, "2021-12-31": 518127906, "2022-03-31": 526829445,
    "2022-06-30": 517107440, "2022-09-30": 521285864, "2022-12-31": 523392860,
    "2023-03-31": 513965560, "2023-06-30": 466552717, "2023-09-30": 487581794,
    "2023-12-31": 468211477, "2024-03-31": 458837032, "2024-06-30": 485350301,
    "2024-09-30": 475437809,
}


def load(path):
    with open(path, newline="") as f:
        rows = list(csv.reader(f))
    dates = rows[0][1:]
    table = {r[0]: {d: (float(v) if v else None) for d, v in zip(dates, r[1:])} for r in rows[1:]}
    return dates, table


def main(shares_path, weights_path, volume_path=None):
    dates, shares = load(shares_path)
    _, weights = load(weights_path)
    net_assets = weights.pop("NETASSETS_USD_M")

    bad = [d for d in dates if round(sum(v[d] or 0 for v in shares.values())) != CHECKSUM[d]]
    print("transcription checksum:", "OK" if not bad else f"MISMATCH on {bad}")

    print("\nSum of holdings above 4.8% at each quarter-end (limit 50%), and Exxon (limit 24%)")
    for d in dates:
        big = {t: w[d] for t, w in weights.items() if w[d] and w[d] > 4.8}
        names = " ".join(f"{t} {v:.1f}" for t, v in sorted(big.items(), key=lambda kv: -kv[1]))
        print(f"  {d}  sum {sum(big.values()):5.1f}%   {names}")

    volume = {}
    if volume_path:
        with open(volume_path, newline="") as f:
            for row in csv.DictReader(f):
                volume[row["ticker"]] = {y: float(v) for y, v in row.items() if y != "ticker"}

    print(f"\nHoldings bought or sold relative to the fund's overall scaling (over {FLAG:.0%})")
    print("  'days' = shares traded / that stock's median daily volume in that year (Yahoo)")
    for d0, d1 in zip(dates, dates[1:]):
        growth = {t: s[d1] / s[d0] for t, s in shares.items() if s[d0] and s[d1]}
        median = statistics.median(growth.values())

        def price(t):
            return weights[t][d1] / 100 * net_assets[d1] * 1e6 / shares[t][d1]

        # Scaling factor that makes the quarter's trades net to zero dollars at
        # quarter-end prices (a rebalance is self-financing). Holdings that left
        # the fund are not in the sum, so the factor is slightly high in those quarters.
        held = [t for t, s in shares.items() if s[d1]]
        common = sum(price(t) * shares[t][d1] for t in held) / sum(price(t) * (shares[t][d0] or 0) for t in held)
        print(f"  {d0} -> {d1}   scaling factor {common:.3f} (median holding grew {median:.3f})")
        for t, g in sorted(growth.items(), key=lambda kv: kv[1]):
            rel = g / common - 1
            if abs(rel) < FLAG:
                continue
            extra_shares = shares[t][d1] - shares[t][d0] * common
            usd_m = extra_shares * price(t) / 1e6
            vol = volume.get(t, {}).get(d1[:4])
            days = f"{abs(extra_shares) / 1e6 / vol:4.1f} days" if vol else "   n/a   "
            print(f"      {t:<5} {rel:+7.1%}   {extra_shares / 1e6:+7.1f}M shares   about ${usd_m:+,.0f}M   {days}"
                  f"   weight {weights[t][d0]:.1f}% -> {weights[t][d1]:.1f}%")
        joined = [t for t, s in shares.items() if not s[d0] and s[d1]]
        left = [t for t, s in shares.items() if s[d0] and not s[d1]]
        if joined or left:
            print(f"      joined: {joined}  left: {left}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
