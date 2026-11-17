"""Compare natural (uncapped) energy weights with what XLE actually held.

Usage: python -I natural_vs_actual_weights.py <ivv_shares.csv> <ivv_value_usd_m.csv> <xle_weights_pct.csv>

Natural weight = a company's share of the energy holdings of an S&P 500 index
fund (iShares IVV, from its SEC N-PORT filings). That fund holds every company
at its uncapped index weight. XLE's weights are the capped ones.
Quarter-ends in the design period only. No returns are computed.
"""
import csv
import sys

CHECKSUM = {
    "2021-09-30": 157228359, "2021-12-31": 169365550, "2022-03-31": 177572021,
    "2022-06-30": 177188050, "2022-09-30": 178532042, "2022-12-31": 183594298,
    "2023-03-31": 181037631, "2023-06-30": 180532721, "2023-09-30": 189398372,
    "2023-12-31": 199312453, "2024-03-31": 204957365, "2024-06-30": 214277183,
    "2024-09-30": 220043464,
}
BIG = ["XOM", "CVX", "COP", "EOG", "SLB"]


def load(path):
    with open(path, newline="") as f:
        rows = list(csv.reader(f))
    dates = rows[0][1:]
    return dates, {r[0]: {d: (float(v) if v else None) for d, v in zip(dates, r[1:])} for r in rows[1:]}


def main(ivv_shares_path, ivv_value_path, xle_weights_path):
    dates, ivv_shares = load(ivv_shares_path)
    _, ivv_value = load(ivv_value_path)
    _, xle = load(xle_weights_path)
    xle.pop("NETASSETS_USD_M", None)

    bad = [d for d in dates if round(sum(v[d] or 0 for v in ivv_shares.values())) != CHECKSUM[d]]
    print("transcription checksum:", "OK" if not bad else f"MISMATCH on {bad}")

    print("\nNatural weight -> weight XLE actually held (%), at each quarter-end")
    print(f"{'date':<12}" + "".join(f"{t:>16}" for t in BIG) + f"{'small-co ratio':>18}")
    for d in dates:
        total = sum(v[d] for v in ivv_value.values() if v[d])
        natural = {t: 100 * v[d] / total for t, v in ivv_value.items() if v[d]}
        cells = "".join(f"{natural[t]:>8.1f} ->{xle[t][d]:>5.1f}" for t in BIG)
        # For companies that were never trimmed, XLE weight / natural weight should be
        # one common number above 1: they all receive the weight taken from the big ones.
        small = sorted(xle[t][d] / natural[t] for t in natural if natural[t] < 4.0 and xle[t][d])
        ratio = f"{small[0]:.2f}-{small[-1]:.2f}"
        print(f"{d:<12}{cells}{ratio:>18}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
