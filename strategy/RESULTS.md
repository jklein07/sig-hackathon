# Futures curve signals (pre-registered in `PREREG_curve.md`)

**Curve data (free, covers the whole sample):**
- USO (front-month WTI fund) vs USL (12-month strip fund).
- Slope = ln(CL=F / CLZ27.NYM), front vs Dec-2027 contract, as a z-score vs trailing 252 days. Correlation with the official EIA M1/M4 slope (through 2024-04): z 0.84, level 0.84.
- EIA stopped publishing NYMEX contract prices in April 2024, and Yahoo drops expired contracts, so a constant-maturity curve isn't available for free.

**Same split:** IS 2021-11-01 to 2024-12-31, OOS 2025-01-01 to 2026-10-30. OOS was run once, after the rule was frozen.

## In-sample
| Test | Result |
|---|---|
| H1: what producer stocks track, same day | XOP β to strip 0.72 (t = 12.9); OIH 0.79 (t = 18.2). Front-minus-strip β ≈ −0.2 (t ≈ −1). **Stocks track the strip, not the front month.** |
| H2: front outran strip → stocks fall later | Best cell t = −1.73. Fails the selection bar. |
| H3: backwardation z → OIH next 20d | **t = −2.49** (5d neighbour t = −2.08). Selected. Below the Bonferroni bar of 2.87. |

**Frozen rule:** OIH position = clip(−slope_z / 2, −1, 1), rebalanced weekly, 10 bp/$ costs. Steep backwardation → short or underweight OIH; flat curve or contango → long.

## Out-of-sample (single run)
| | IS | OOS |
|---|---|---|
| Predictive regression t (OIH h = 20) | −2.52 | −0.64 (same sign, much weaker) |
| Strategy Sharpe | 0.62 | **0.85** |
| Strategy ann. return / vol / maxDD | +11.4% / 18% / −11.5% | +18.2% / 21% / −18.9% |
| OIH buy-and-hold Sharpe / maxDD | 0.42 / −36% | 0.87 / −34% |
| Alpha vs OIH B&H (HAC) | +11.0%/yr, t = 1.52 | +11.6%/yr, t = 0.96 |
| Average position | +0.38 | +0.09 |

**Pre-registered criterion (OOS Sharpe > 0, OOS alpha > 0, same sign as IS): met.**

## Audit
- **Weak statistically.** With 20-day horizons there are only about 22 independent OOS observations. The smallest correlation detectable at 80% power is about 0.6, so the OOS test can't confirm or reject the effect. The alpha t-stats (1.5 IS, 1.0 OOS) are not significant.
- **Unlike the crack rule, this isn't hidden exposure.** The OOS average position is +0.09 (roughly neutral) and beta to OIH is 0.22. It matched OIH's Sharpe with about 60% of the volatility and about half the drawdown.
- **Robustness (added after the test):** z-windows 126/252/504 → OOS Sharpe 0.84/0.85/0.85 (similar by coincidence, positions differ; IS 1.16/0.62/−0.05, so not stable in IS). The same rule on XOP: OOS Sharpe 0.57. The 5d horizon on OIH OOS: t = −1.04, same sign.
- **Uneven by year:** 2022 −0.4%, 2023 +22.2%, 2024 +1.2%, 2025 +33.7%, 2026 0.0%. It did nothing during the 2026 Hormuz shock.
- **Proxy limits:** the CLZ27 tenor shrinks from about 6 years to about 1 year over the sample. The trailing z-score absorbs some of this, but not all.

## Bottom line for the hackathon
- **Solid finding:** energy equities price off the 12-month strip, not the front month (t ≈ 13–18).
- **Tradable idea with honest caveats:** the backwardation signal on OIH passed a pre-registered OOS test (Sharpe 0.85, half the drawdown of buy-and-hold). The evidence is weak (alpha t ≈ 1), so present it as promising, not proven.

# History test: frozen rule on 2001–2021 (pre-registered in `PREREG_history.md`)

Same rule, same settings, run once. The one forced change: the signal is ln(EIA month 1 / month 4) because Dec-2027 doesn't exist before 2021. OIH from Yahoo (adjusted), 2001-02-26 to 2021-10-29, 5,204 days. Data check: no jumps at the Dec-2011 sponsor change; the largest moves are real crisis days (Oct 2008, Mar 2020).

| | Result |
|---|---|
| **Primary: OIH 20d fwd ~ z** | beta −0.0027, t = −0.71 → **FAIL** (needed t ≤ −1.65) |
| MDE (80% power) | \|beta\| ≥ 0.0093. The live in-sample estimate was −0.0217, so an effect that size would have been caught. |
| Strategy | +0.5%/yr, vol 24%, Sharpe 0.02, maxDD −84%, $1 → $0.60 |
| OIH buy-and-hold | +4.5%/yr, vol 40%, Sharpe 0.11, maxDD −94%, $1 → $0.50 |
| Alpha vs OIH | −0.3%/yr, t = −0.07 |

Sub-periods (regression t / strategy Sharpe vs OIH): 2001–07 −1.96 / 0.61 vs 0.54; 2008–13 **+1.73** / −0.28 vs 0.14; 2014–21 −0.69 / −0.15 vs −0.20. The sign flips across decades.

**Diagnostic (added after the test):** on the same 339 days of 2022-10..2024-04, the live slope predicts OIH (t = −2.04) but the EIA month-1/month-4 slope doesn't (t = −0.62), even though their z-scores correlate 0.89. So the history test can't fully stand in for the real signal. It also shows the live result depends heavily on exactly how the slope is built, which is itself a fragility warning.

## Updated bottom line
- An effect the size we found in 2022–24 does not appear in 20 years of near-curve data.
- Either the effect lives only in the long-dated part of the curve (untestable before 2021 with free data), or the 2022–26 result was a regime or luck. We can't tell which.
- Pitch it as: worked over 2022–26 with a pre-registered out-of-sample pass, did not show up in a 20-year check with the closest available proxy. Not proven, possibly regime-specific.
