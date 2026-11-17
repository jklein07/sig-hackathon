# Timing OIH with the Oil Futures Curve

Team 1: Riveen, Jon, Prakrit. We trade one fund, OIH. We short it when oil for next month is unusually expensive compared with oil for December 2027, and buy it when that difference is unusually small.

## 1. Strategy type and why

This is a signal-based timing strategy. One number from the oil futures market decides whether we hold OIH long or short and how much. We chose this over momentum or pairs trading because the reason we expect OIH to move comes from the oil market, not from OIH's own price history.

The companies in OIH, such as SLB and Halliburton, get paid when producers drill, and producers plan drilling around prices a year or more out. From 2021-11-01 to 2024-12-31, XOP and OIH moved closely with the 12-month oil strip (USL fund, t = 12.9 and 18.2) and showed no extra reaction to the front month on its own (t near -1). So when only near-term oil is high, drilling budgets barely change, and OIH tends to lag.

## 2. Asset selection

We trade only OIH and keep the rest in cash, for three reasons.

- Its companies' revenue depends on drilling budgets, which producers set using longer-dated prices.
- It had the strongest result of the 12 fund-and-signal pairs we tested on 2021-24 data. A large gap came before weaker OIH returns over the next 20 days (t = -2.49). XOP was weaker (t = -1.60), likely because producers still sell oil at today's price.
- It holds about 25 companies, so news about any one of them has little effect.

## 3. Core framework

1. Each day, compute the gap as ln(front-month WTI / Dec-2027 WTI), using Yahoo CL=F and CLZ27.NYM.
2. Turn it into a z-score: z = (gap - its 252-trading-day mean) / its 252-trading-day standard deviation.
3. Set the position in OIH to -z / 2, capped at -100% (short) and +100% (long). A z of +2 or more means fully short, -2 or less means fully long, and 0 means no position.
4. Rebalance every 5 trading days at the close. The new position earns the next day's return, and each dollar traded costs 0.10%.

Two real examples: on 2026-03-06 the gap was +40% when it was usually about +3% (z = 6.6), so we were 100% short. On 2025-04-07 z was -2.2, so we were 100% long. We chose the rule using only 2021-11-01 to 2024-12-31 and wrote it down before running 2025-01-01 to 2026-10-30 once.

## 4. Risk management

The position grows with the signal but stays within 100% long or short, with no leverage, and the average position was about half that size. Rebalancing weekly keeps trading costs low. Before trading real money we would add three things that are not in these results: cut the position in half after a 15% drawdown, switch to a later December contract before Dec 2027, and pay the fee to borrow OIH when short.

The main risks:

- The test covers only about 22 months, and the extra return has a t-stat of about 1, so it could be luck.
- Geopolitical shocks can swamp the signal. The strategy made nothing during the 2026 Hormuz disruption.
- A sudden oil spike while we are short would hurt. The 100% cap limits the loss.
- The Dec-2027 contract gets closer every year, which slowly changes what the gap measures.
- We have not shown it works before 2022. The same rule on 2001-21 EIA data (months 1 and 4 only) showed no effect.

## Results

The rule passed the test we set in advance. It earned about the same return per unit of risk as holding OIH, with roughly half the worst drop. $1 grew to $1.65, compared with $1.51 for holding OIH (2022-11 to 2026-10, after costs).

| | Build (2021-11 to 2024-12) | Test (2025-01 to 2026-10) |
|---|---|---|
| Sharpe, ours / OIH | 0.62 / 0.42 | 0.85 / 0.87 |
| Worst drop, ours / OIH | -12% / -36% | -19% / -34% |
| Extra return vs OIH, per year | +11.0% (t = 1.5) | +11.6% (t = 1.0) |

Data: the hackathon dataset (Yahoo adjusted close, 2021-11-01 to 2026-10-30), plus Yahoo CL=F and CLZ27.NYM futures prices for the signal. The z-score needs a year of history, so our trading starts in Nov 2022, while the OIH figures cover the full period.
