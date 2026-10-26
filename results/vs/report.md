# Volatility-aware NIFTY 50 stock selection: walk-forward results

**Academic research prototype. Not investment advice.** Past backtest results do not predict future returns.

50 current NIFTY 50 stocks, data to 2026-10-23. Models refitted every 1 January on past data only. Weekly rebalance, top 10, inverse-volatility weights, 0.15% cost per side, signals at the close, fills at the next open. Drawdown trigger chosen on 2016–2021 Calmar only: 12%.

## Full walk-forward 2016–2026

| Approach | CAGR % | Sharpe | Max drawdown % | Worst day % | Days below -2% (count) | Calmar | Turnover (x/yr) |
|---|---|---|---|---|---|---|---|
| Regime switch (LR), no trigger | 17.10 | 0.61 | -33.84 | -12.26 | 103.00 | 0.51 | 35.01 |
| Regime switch (LR) + 8% trigger | 13.28 | 0.46 | -43.13 | -11.28 | 69.00 | 0.31 | 25.87 |
| Regime switch (LR) + 10% trigger | 14.87 | 0.53 | -43.94 | -11.28 | 77.00 | 0.34 | 26.50 |
| Regime switch (LR) + 12% trigger | 18.04 | 0.69 | -34.49 | -12.07 | 77.00 | 0.52 | 31.65 |
| Regime switch (GB), no trigger | 19.35 | 0.71 | -35.14 | -12.07 | 105.00 | 0.55 | 36.51 |
| Momentum only | 19.47 | 0.71 | -36.50 | -11.28 | 113.00 | 0.53 | 22.31 |
| Stress model only | 15.11 | 0.58 | -34.82 | -12.26 | 42.00 | 0.43 | 33.47 |
| Low volatility only | 12.00 | 0.42 | -37.40 | -12.57 | 42.00 | 0.32 | 32.35 |
| Equal-weight NIFTY 50 (benchmark) | 20.32 | 0.84 | -38.40 | -13.11 | 61.00 | 0.53 | 1.45 |
| NIFTY 50 buy and hold (benchmark) | 10.36 | 0.30 | -38.44 | -12.98 | 61.00 | 0.27 | nan |

## Development 2016–2021

| Approach | CAGR % | Sharpe | Max drawdown % | Worst day % | Days below -2% (count) | Calmar | Turnover (x/yr) |
|---|---|---|---|---|---|---|---|
| Regime switch (LR), no trigger | 23.58 | 0.84 | -33.84 | -12.26 | 69.00 | 0.70 | 33.77 |
| Regime switch (LR) + 8% trigger | 17.86 | 0.66 | -43.13 | -11.28 | 47.00 | 0.41 | 35.21 |
| Regime switch (LR) + 10% trigger | 21.31 | 0.79 | -43.94 | -11.28 | 51.00 | 0.48 | 31.59 |
| Regime switch (LR) + 12% trigger | 27.76 | 1.07 | -34.49 | -12.07 | 47.00 | 0.81 | 41.76 |
| Regime switch (GB), no trigger | 27.40 | 0.99 | -35.14 | -12.07 | 70.00 | 0.78 | 36.51 |
| Momentum only | 28.19 | 1.03 | -36.50 | -11.28 | 71.00 | 0.77 | 21.03 |
| Stress model only | 21.03 | 0.83 | -34.82 | -12.26 | 31.00 | 0.60 | 36.20 |
| Low volatility only | 17.74 | 0.72 | -37.40 | -12.57 | 25.00 | 0.47 | 30.30 |
| Equal-weight NIFTY 50 (benchmark) | 24.43 | 0.97 | -38.40 | -13.11 | 40.00 | 0.64 | 1.61 |
| NIFTY 50 buy and hold (benchmark) | 14.30 | 0.49 | -38.44 | -12.98 | 41.00 | 0.37 | nan |

## Hold-out 2022–2026

| Approach | CAGR % | Sharpe | Max drawdown % | Worst day % | Days below -2% (count) | Calmar | Turnover (x/yr) |
|---|---|---|---|---|---|---|---|
| Regime switch (LR), no trigger | 9.39 | 0.24 | -28.86 | -8.14 | 34.00 | 0.33 | 36.61 |
| Regime switch (LR) + 8% trigger | 7.71 | 0.15 | -24.20 | -5.58 | 22.00 | 0.32 | 14.27 |
| Regime switch (LR) + 10% trigger | 7.20 | 0.11 | -26.62 | -5.58 | 26.00 | 0.27 | 20.18 |
| Regime switch (LR) + 12% trigger | 6.84 | 0.09 | -26.63 | -5.58 | 30.00 | 0.26 | 19.09 |
| Regime switch (GB), no trigger | 9.91 | 0.27 | -27.35 | -8.14 | 35.00 | 0.36 | 36.59 |
| Momentum only | 9.32 | 0.24 | -27.05 | -8.14 | 42.00 | 0.34 | 23.95 |
| Stress model only | 8.13 | 0.18 | -20.81 | -3.93 | 11.00 | 0.39 | 30.12 |
| Low volatility only | 5.11 | -0.04 | -21.67 | -4.86 | 17.00 | 0.24 | 34.97 |
| Equal-weight NIFTY 50 (benchmark) | 15.14 | 0.62 | -16.30 | -5.58 | 21.00 | 0.93 | 1.24 |
| NIFTY 50 buy and hold (benchmark) | 5.31 | -0.02 | -16.47 | -5.93 | 20.00 | 0.32 | nan |

## COVID crash (14 Feb–30 Apr 2020)

| Approach | CAGR % | Sharpe | Max drawdown % | Worst day % | Days below -2% (count) | Calmar | Turnover (x/yr) | Period return % |
|---|---|---|---|---|---|---|---|---|
| Regime switch (LR), no trigger | -50.01 | -1.06 | -33.61 | -12.26 | 12.00 | -1.49 | 51.32 | -13.43 |
| Regime switch (LR) + 8% trigger | -53.81 | -1.35 | -35.88 | -11.28 | 9.00 | -1.50 | 28.66 | -14.85 |
| Regime switch (LR) + 10% trigger | -53.81 | -1.35 | -35.88 | -11.28 | 9.00 | -1.50 | 28.66 | -14.85 |
| Regime switch (LR) + 12% trigger | -29.98 | -0.47 | -32.77 | -12.07 | 10.00 | -0.91 | 55.51 | -7.15 |
| Regime switch (GB), no trigger | -43.07 | -0.83 | -35.14 | -12.07 | 12.00 | -1.23 | 54.46 | -11.06 |
| Momentum only | -55.81 | -1.43 | -36.50 | -11.28 | 10.00 | -1.53 | 17.13 | -15.63 |
| Stress model only | -46.30 | -0.93 | -33.11 | -12.26 | 11.00 | -1.40 | 48.11 | -12.14 |
| Low volatility only | -47.54 | -1.07 | -35.16 | -12.57 | 8.00 | -1.35 | 43.13 | -12.56 |
| Equal-weight NIFTY 50 (benchmark) | -64.61 | -1.75 | -37.68 | -13.11 | 13.00 | -1.71 | 2.57 | -19.44 |
| NIFTY 50 buy and hold (benchmark) | -62.81 | -1.56 | -37.24 | -12.98 | 14.00 | -1.69 | nan | -18.60 |

## 2022 sell-off (Jan–Jun 2022)

| Approach | CAGR % | Sharpe | Max drawdown % | Worst day % | Days below -2% (count) | Calmar | Turnover (x/yr) | Period return % |
|---|---|---|---|---|---|---|---|---|
| Regime switch (LR), no trigger | -12.56 | -0.86 | -14.72 | -3.94 | 8.00 | -0.85 | 49.82 | -6.33 |
| Regime switch (LR) + 8% trigger | -24.66 | -1.51 | -18.92 | -5.14 | 8.00 | -1.30 | 21.74 | -12.89 |
| Regime switch (LR) + 10% trigger | -19.00 | -1.22 | -16.72 | -4.14 | 9.00 | -1.14 | 46.86 | -9.76 |
| Regime switch (LR) + 12% trigger | -22.91 | -1.35 | -18.88 | -5.14 | 10.00 | -1.21 | 24.56 | -11.91 |
| Regime switch (GB), no trigger | -12.35 | -0.82 | -17.20 | -4.06 | 8.00 | -0.72 | 56.40 | -6.22 |
| Momentum only | -24.89 | -1.46 | -19.73 | -5.02 | 11.00 | -1.26 | 27.76 | -13.02 |
| Stress model only | -6.42 | -0.60 | -10.06 | -3.93 | 5.00 | -0.64 | 33.23 | -3.18 |
| Low volatility only | -25.99 | -1.93 | -17.85 | -3.71 | 4.00 | -1.46 | 35.11 | -13.64 |
| Equal-weight NIFTY 50 (benchmark) | -15.90 | -1.02 | -14.22 | -5.14 | 8.00 | -1.12 | 1.56 | -8.09 |
| NIFTY 50 buy and hold (benchmark) | -20.30 | -1.32 | -16.47 | -4.78 | 9.00 | -1.23 | nan | -10.47 |

## Days the forecast said rising or high

| Approach | Annualised return on forecast rising/high days % | Days |
|---|---|---|
| Regime switch (LR), no trigger | -26.3 | 549.0 |
| Regime switch (LR) + 8% trigger | -32.8 | 549.0 |
| Regime switch (LR) + 10% trigger | -24.5 | 549.0 |
| Regime switch (LR) + 12% trigger | -18.3 | 549.0 |
| Regime switch (GB), no trigger | -21.3 | 549.0 |
| Momentum only | -24.0 | 549.0 |
| Stress model only | -3.7 | 549.0 |
| Low volatility only | -24.7 | 549.0 |
| Equal-weight NIFTY 50 (benchmark) | -19.7 | 549.0 |
| NIFTY 50 buy and hold (benchmark) | -30.8 | 549.0 |

## Volatility forecast accuracy (high = p ≥ 0.5 vs naive 'next 10 days like the last 10')

**Development 2016–2021:** 1476 days, 23% actually high. Hit rate 76.2% (naive 78.3%); precision 47.1%; recall 19.2% (naive 52.5%).

| actual | forecast not high | forecast high |
|---|---|---|
| actual not high | 1059 | 74 |
| actual high | 277 | 66 |

**Hold-out 2022–2026:** 1177 days, 29% actually high. Hit rate 72.9% (naive 67.5%); precision 72.5%; recall 10.8% (naive 42.4%).

| actual | forecast not high | forecast high |
|---|---|---|
| actual not high | 821 | 14 |
| actual high | 305 | 37 |

## Drawdown trigger thresholds

| Trigger | Calmar 2016–2021 | Calmar 2022+ | Triggers |
|---|---|---|---|
| 8% | 0.41 | 0.32 | 19.00 |
| 10% | 0.48 | 0.27 | 12.00 |
| 12% | 0.81 | 0.26 | 9.00 |

## Overfitting checks

Feature information coefficients on high-volatility days:

| Feature | IC 2013–2021 (high-vol days) | IC 2022+ (high-vol days) | Flag |
|---|---|---|---|
| beta | -0.060 | nan | looked useful before 2022, failed after |
| down_beta | -0.042 | nan | looked useful before 2022, failed after |
| hv_excess | -0.014 | nan |  |
| defensive | 0.054 | nan | looked useful before 2022, failed after |
| rel_strength | -0.009 | nan |  |
| liquidity | -0.040 | nan | looked useful before 2022, failed after |
| rsi | -0.031 | nan | looked useful before 2022, failed after |
| macd | -0.015 | nan |  |
| adx | 0.016 | nan |  |
| pct_b | -0.043 | nan | looked useful before 2022, failed after |
| atr_pct | -0.001 | nan |  |
| obv_trend | -0.003 | nan |  |
| stoch | -0.038 | nan | looked useful before 2022, failed after |
| ma50_dist | -0.018 | nan |  |
| ma200_dist | 0.000 | nan |  |
| mom_20 | -0.016 | nan |  |
| mom_60 | -0.009 | nan |  |
| mom_120 | -0.014 | nan |  |
| vol_20 | -0.020 | nan |  |

Gradient boosting vs logistic regression (stress model):

| Year | GB in-sample AUC | GB out-of-sample AUC | LR out-of-sample AUC |
|---|---|---|---|
| 2016 | 0.843 | 0.513 | 0.481 |
| 2017 | 0.834 | 0.560 | 0.565 |
| 2018 | 0.841 | 0.544 | 0.557 |
| 2019 | 0.803 | 0.477 | 0.496 |
| 2020 | 0.788 | 0.545 | 0.545 |
| 2021 | 0.761 | 0.493 | 0.479 |
| 2022 | 0.759 | 0.542 | 0.532 |
| 2023 | 0.746 | 0.572 | 0.543 |
| 2024 | 0.737 | 0.497 | 0.516 |
| 2025 | 0.734 | 0.459 | 0.389 |
| 2026 | 0.729 | 0.500 | 0.520 |

**Flags:**

- The best drawdown trigger before 2022 (12%) was not the best after 2022 (8%).
- Gradient boosting fits its training data much better than new data (average AUC gap 0.26): overfitting.
- Feature 'beta' looked useful in high-volatility periods before 2022 but did not hold after.
- Feature 'down_beta' looked useful in high-volatility periods before 2022 but did not hold after.
- Feature 'defensive' looked useful in high-volatility periods before 2022 but did not hold after.
- Feature 'liquidity' looked useful in high-volatility periods before 2022 but did not hold after.
- Feature 'rsi' looked useful in high-volatility periods before 2022 but did not hold after.
- Feature 'pct_b' looked useful in high-volatility periods before 2022 but did not hold after.
- Feature 'stoch' looked useful in high-volatility periods before 2022 but did not hold after.

## Limitations

- Survivorship bias: today's NIFTY 50 list is used for all years; no free point-in-time constituent list exists. This flatters every approach that holds these stocks, including the equal-weight benchmark.
- Yahoo Finance data is unofficial; VIX futures term structure was not available and is not used.
- Daily data only; the drawdown trigger acts at the next open.
- One market, one decade: 2022 onward is a short hold-out.
- Long-only cash segment; no shorting or derivatives hedges.

## Compliance

Offering stock selections to customers requires SEBI Research Analyst registration, and running the algorithm for clients requires exchange empanelment through a broker and algo registration. This prototype is not offered to anyone.
