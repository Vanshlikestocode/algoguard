# AlgoGuard results

Data: NSE daily data via Yahoo Finance. 12 stocks, 2012-01-02 to 2026-10-16, 3645 sessions. Capital Rs 10 lakh, costs 0.15% per side, signals at close, fills next open.

## 1. Raw strategy vs strategy + guardrails

| Strategy | risk layer | CAGR % | Sharpe | Max drawdown % | Worst day % | Days below -2% (count) | Calmar | Trades | Avg exposure % |
|---|---|---|---|---|---|---|---|---|---|
| EMA Crossover (20/100) | Raw | 7.59 | 0.14 | -18.33 | -6.89 | 27.00 | 0.41 | 289.00 | 69.50 |
| EMA Crossover (20/100) | Guarded | 6.35 | 0.03 | -18.45 | -7.30 | 20.00 | 0.34 | 289.00 | 62.04 |
| Donchian Breakout (55/20) | Raw | 3.77 | -0.32 | -14.13 | -5.29 | 8.00 | 0.27 | 351.00 | 44.07 |
| Donchian Breakout (55/20) | Guarded | 2.85 | -0.48 | -13.98 | -7.57 | 5.00 | 0.20 | 348.00 | 39.02 |
| RSI-2 Mean Reversion | Raw | -0.21 | -1.75 | -10.29 | -2.69 | 1.00 | -0.02 | 1161.00 | 12.84 |
| RSI-2 Mean Reversion | Guarded | -1.03 | -2.06 | -16.34 | -2.02 | 1.00 | -0.06 | 1095.00 | 12.78 |
| NIFTY 50 buy & hold | 11.28 | 0.36 | -38.44 | -12.98 | 86.00 | 0.29 | nan | nan |

## 2. In-sample vs out-of-sample (split 2022-01-01)

All parameters are textbook defaults fixed before testing, so the out-of-sample period is a genuine hold-out.

| Strategy | layer | period | CAGR % | Sharpe | Max drawdown % | Worst day % |
|---|---|---|---|---|---|---|
| EMA Crossover (20/100) | Raw | In-sample | 9.86 | 0.33 | -18.33 | -5.16 |
| EMA Crossover (20/100) | Raw | Out-of-sample | 2.77 | -0.33 | -14.81 | -6.89 |
| EMA Crossover (20/100) | Guarded | In-sample | 8.26 | 0.21 | -18.45 | -4.41 |
| EMA Crossover (20/100) | Guarded | Out-of-sample | 2.24 | -0.38 | -14.54 | -7.30 |
| Donchian Breakout (55/20) | Raw | In-sample | 5.04 | -0.14 | -14.13 | -3.16 |
| Donchian Breakout (55/20) | Raw | Out-of-sample | 1.13 | -0.80 | -10.59 | -5.29 |
| Donchian Breakout (55/20) | Guarded | In-sample | 3.26 | -0.41 | -13.98 | -7.57 |
| Donchian Breakout (55/20) | Guarded | Out-of-sample | 2.00 | -0.63 | -9.95 | -5.12 |
| RSI-2 Mean Reversion | Raw | In-sample | 0.42 | -1.52 | -8.18 | -1.56 |
| RSI-2 Mean Reversion | Raw | Out-of-sample | -1.50 | -2.29 | -8.98 | -2.69 |
| RSI-2 Mean Reversion | Guarded | In-sample | -0.72 | -2.00 | -16.34 | -1.94 |
| RSI-2 Mean Reversion | Guarded | Out-of-sample | -1.66 | -2.16 | -8.83 | -2.02 |

## 3. Ablation: contribution of each rule

Each rule switched on alone (vs raw), and each rule removed from the full set.

| Strategy | rule | Only this rule: Sharpe | Only this rule: Max DD % | Max DD change vs raw (pts) | All rules except this: Sharpe | All except this: Max DD % |
|---|---|---|---|---|---|---|
| EMA Crossover (20/100) | ATR stop-loss | 0.05 | -16.70 | 1.63 | 0.16 | -18.24 |
| EMA Crossover (20/100) | Daily loss limit | 0.14 | -18.33 | 0.00 | 0.02 | -18.50 |
| EMA Crossover (20/100) | Losing-streak cooldown | 0.14 | -18.15 | 0.18 | 0.03 | -18.75 |
| EMA Crossover (20/100) | Drawdown circuit breaker | 0.13 | -19.70 | -1.37 | 0.02 | -18.89 |
| EMA Crossover (20/100) | India VIX filter | 0.11 | -19.04 | -0.71 | 0.06 | -17.59 |
| EMA Crossover (20/100) | Volatility sizing | 0.20 | -16.96 | 1.37 | -0.03 | -19.00 |
| Donchian Breakout (55/20) | ATR stop-loss | -0.48 | -14.39 | -0.26 | -0.33 | -13.57 |
| Donchian Breakout (55/20) | Daily loss limit | -0.32 | -14.13 | 0.00 | -0.48 | -13.98 |
| Donchian Breakout (55/20) | Losing-streak cooldown | -0.32 | -14.13 | 0.00 | -0.48 | -13.96 |
| Donchian Breakout (55/20) | Drawdown circuit breaker | -0.32 | -14.13 | 0.00 | -0.48 | -13.98 |
| Donchian Breakout (55/20) | India VIX filter | -0.34 | -14.13 | 0.00 | -0.47 | -13.99 |
| Donchian Breakout (55/20) | Volatility sizing | -0.31 | -13.58 | 0.55 | -0.50 | -14.51 |
| RSI-2 Mean Reversion | ATR stop-loss | -2.03 | -12.73 | -2.44 | -1.81 | -12.31 |
| RSI-2 Mean Reversion | Daily loss limit | -1.75 | -10.29 | 0.00 | -2.06 | -16.34 |
| RSI-2 Mean Reversion | Losing-streak cooldown | -1.76 | -10.34 | -0.06 | -2.12 | -20.07 |
| RSI-2 Mean Reversion | Drawdown circuit breaker | -1.75 | -10.29 | 0.00 | -2.07 | -16.98 |
| RSI-2 Mean Reversion | India VIX filter | -1.87 | -10.01 | 0.27 | -2.01 | -15.89 |
| RSI-2 Mean Reversion | Volatility sizing | -1.72 | -10.84 | -0.55 | -2.10 | -13.20 |

## 4. Parameter robustness (EMA crossover, 10 settings)

Guardrails should help across settings, not just at one lucky parameter choice.

| Across 10 EMA settings | Raw Sharpe | Raw MaxDD % | Guarded Sharpe | Guarded MaxDD % |
|---|---|---|---|---|
| mean | 0.15 | -19.94 | 0.06 | -17.04 |
| min | 0.03 | -27.99 | -0.05 | -21.85 |
| max | 0.22 | -15.92 | 0.21 | -13.47 |

## 5. Transaction-cost sensitivity

| Strategy | layer | cost per side | CAGR % | Sharpe | Max drawdown % |
|---|---|---|---|---|---|
| EMA Crossover (20/100) | Raw | 0.05% | 7.92 | 0.17 | -17.82 |
| EMA Crossover (20/100) | Guarded | 0.05% | 6.56 | 0.05 | -17.88 |
| EMA Crossover (20/100) | Raw | 0.15% | 7.59 | 0.14 | -18.33 |
| EMA Crossover (20/100) | Guarded | 0.15% | 6.35 | 0.03 | -18.45 |
| EMA Crossover (20/100) | Raw | 0.30% | 7.16 | 0.11 | -19.02 |
| EMA Crossover (20/100) | Guarded | 0.30% | 5.15 | -0.09 | -24.62 |
| Donchian Breakout (55/20) | Raw | 0.05% | 4.18 | -0.26 | -13.76 |
| Donchian Breakout (55/20) | Guarded | 0.05% | 3.26 | -0.42 | -13.60 |
| Donchian Breakout (55/20) | Raw | 0.15% | 3.77 | -0.32 | -14.13 |
| Donchian Breakout (55/20) | Guarded | 0.15% | 2.85 | -0.48 | -13.98 |
| Donchian Breakout (55/20) | Raw | 0.30% | 3.17 | -0.39 | -14.71 |
| Donchian Breakout (55/20) | Guarded | 0.30% | 2.24 | -0.56 | -14.55 |
| RSI-2 Mean Reversion | Raw | 0.05% | 1.10 | -1.40 | -7.49 |
| RSI-2 Mean Reversion | Guarded | 0.05% | 0.29 | -1.68 | -11.52 |
| RSI-2 Mean Reversion | Raw | 0.15% | -0.21 | -1.75 | -10.29 |
| RSI-2 Mean Reversion | Guarded | 0.15% | -1.03 | -2.06 | -16.34 |
| RSI-2 Mean Reversion | Raw | 0.30% | -2.14 | -2.27 | -27.81 |
| RSI-2 Mean Reversion | Guarded | 0.30% | -3.24 | -2.71 | -39.25 |

## 6. How often the guardrails intervened

Every intervention is in the audit log CSVs (date, rule, action, detail).

| Strategy | ATR stops hit | Halts (drawdown) | Daily-loss cooldowns | Losing-streak pauses | Entries blocked: India VIX filter | Entries blocked: Losing-streak cooldown | Entries blocked: Daily loss limit | Entries blocked: Drawdown circuit breaker |
|---|---|---|---|---|---|---|---|---|
| EMA Crossover (20/100) | 91 | 2 | 20 | 45 | 247 | 48 | 2 | 107 |
| Donchian Breakout (55/20) | 114 | 0 | 5 | 46 | 211 | 42 | 2 | 0 |
| RSI-2 Mean Reversion | 87 | 1 | 1 | 60 | 124 | 157 | 0 | 19 |

## 7. Guarded v2: strategy-aware guardrails

Each strategy picks its own drawdown-breaker mode, VIX filter and stop distance from a fixed menu of 16 settings. The choice is made by highest Calmar on data before 2022-01-01 only, then run once on the out-of-sample period. All other rules are unchanged from v1.

Chosen settings:

- EMA Crossover (20/100): breaker: sell all, VIX filter: off, stop: 4x ATR
- Donchian Breakout (55/20): breaker: sell all, VIX filter: off, stop: none
- RSI-2 Mean Reversion: breaker: sell all, VIX filter: off, stop: none

| Strategy | layer | period | CAGR % | Sharpe | Max drawdown % | Worst day % | Days below -2% (count) | Calmar |
|---|---|---|---|---|---|---|---|---|
| EMA Crossover (20/100) | Raw | In-sample | 9.86 | 0.33 | -18.33 | -5.16 | 22.00 | 0.54 |
| EMA Crossover (20/100) | Raw | Out-of-sample | 2.77 | -0.33 | -14.81 | -6.89 | 5.00 | 0.19 |
| EMA Crossover (20/100) | Guarded v1 | In-sample | 8.26 | 0.21 | -18.45 | -4.41 | 15.00 | 0.45 |
| EMA Crossover (20/100) | Guarded v1 | Out-of-sample | 2.24 | -0.38 | -14.54 | -7.30 | 5.00 | 0.15 |
| EMA Crossover (20/100) | Guarded v2 | In-sample | 9.60 | 0.33 | -17.07 | -4.78 | 16.00 | 0.56 |
| EMA Crossover (20/100) | Guarded v2 | Out-of-sample | 2.32 | -0.36 | -15.13 | -7.49 | 5.00 | 0.15 |
| Donchian Breakout (55/20) | Raw | In-sample | 5.04 | -0.14 | -14.13 | -3.16 | 7.00 | 0.36 |
| Donchian Breakout (55/20) | Raw | Out-of-sample | 1.13 | -0.80 | -10.59 | -5.29 | 1.00 | 0.11 |
| Donchian Breakout (55/20) | Guarded v1 | In-sample | 3.26 | -0.41 | -13.98 | -7.57 | 4.00 | 0.23 |
| Donchian Breakout (55/20) | Guarded v1 | Out-of-sample | 2.00 | -0.63 | -9.95 | -5.12 | 1.00 | 0.20 |
| Donchian Breakout (55/20) | Guarded v2 | In-sample | 5.01 | -0.16 | -13.58 | -2.41 | 4.00 | 0.37 |
| Donchian Breakout (55/20) | Guarded v2 | Out-of-sample | 1.51 | -0.65 | -11.86 | -5.29 | 1.00 | 0.13 |
| RSI-2 Mean Reversion | Raw | In-sample | 0.42 | -1.52 | -8.18 | -1.56 | 0.00 | 0.05 |
| RSI-2 Mean Reversion | Raw | Out-of-sample | -1.50 | -2.29 | -8.98 | -2.69 | 1.00 | -0.17 |
| RSI-2 Mean Reversion | Guarded v1 | In-sample | -0.72 | -2.00 | -16.34 | -1.94 | 0.00 | -0.04 |
| RSI-2 Mean Reversion | Guarded v1 | Out-of-sample | -1.66 | -2.16 | -8.83 | -2.02 | 1.00 | -0.19 |
| RSI-2 Mean Reversion | Guarded v2 | In-sample | 0.03 | -1.60 | -11.12 | -1.89 | 0.00 | 0.00 |
| RSI-2 Mean Reversion | Guarded v2 | Out-of-sample | -1.46 | -1.96 | -9.60 | -2.43 | 1.00 | -0.15 |
| NIFTY 50 buy & hold | In-sample | 13.80 | 0.48 | -38.44 | -12.98 | 66.00 | 0.36 |
| NIFTY 50 buy & hold | Out-of-sample | 5.86 | 0.02 | -16.47 | -5.93 | 20.00 | 0.36 |

Every candidate's in-sample score is in `7_v2_candidates_in_sample.csv`.

## 8. Walk-forward (2015 to 2026)

Every 1 January the v2 setting is re-picked from the same 16-setting menu using only data before that date, then used for that year. Every year is out-of-sample for the setting it uses. The setting picked each year is in `8_walk_forward_picks.csv`.

| Strategy | layer | CAGR % | Sharpe | Max drawdown % | Days below -2% (count) | Calmar |
|---|---|---|---|---|---|---|
| EMA Crossover (20/100) | Raw | 6.94 | 0.09 | -16.30 | 24.00 | 0.43 |
| EMA Crossover (20/100) | Guarded v1 | 5.58 | -0.05 | -18.45 | 18.00 | 0.30 |
| EMA Crossover (20/100) | Walk-forward v2 | 6.37 | 0.03 | -19.20 | 22.00 | 0.33 |
| Donchian Breakout (55/20) | Raw | 2.89 | -0.44 | -14.13 | 8.00 | 0.20 |
| Donchian Breakout (55/20) | Guarded v1 | 2.34 | -0.58 | -13.98 | 4.00 | 0.17 |
| Donchian Breakout (55/20) | Walk-forward v2 | 2.90 | -0.45 | -13.58 | 5.00 | 0.21 |
| RSI-2 Mean Reversion | Raw | 0.24 | -1.63 | -10.29 | 1.00 | 0.02 |
| RSI-2 Mean Reversion | Guarded v1 | -0.54 | -1.92 | -9.69 | 1.00 | -0.06 |
| RSI-2 Mean Reversion | Walk-forward v2 | 0.05 | -1.58 | -10.85 | 1.00 | 0.00 |

## 9. Trade statistics (win/loss)

Every round trip, after costs on both sides. A trade that only covered its costs counts as a loss. Out-of-sample = trades entered on or after the split date. Positions still open at the end are closed at the last close for these statistics only. Full columns in `9_trade_stats.csv`.

| Strategy | layer | trades entered | Trades | Win rate % | Win/loss count ratio | Avg win % | Avg loss % | Payoff ratio (avg win / avg loss) | Profit factor | Expectancy per trade % | Max losing streak (trades) | Avg holding (calendar days) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| EMA Crossover (20/100) | Raw | 2012-2026 | 289.00 | 34.60 | 0.53 | 26.54 | -5.86 | 4.53 | 2.16 | 5.35 | 17.00 | 143.71 |
| EMA Crossover (20/100) | Raw | Out-of-sample | 95.00 | 33.68 | 0.51 | 19.45 | -5.76 | 3.37 | 1.60 | 2.73 | 16.00 | 124.35 |
| EMA Crossover (20/100) | Guarded v1 | 2012-2026 | 289.00 | 31.49 | 0.46 | 25.63 | -5.41 | 4.73 | 2.04 | 4.36 | 13.00 | 127.87 |
| EMA Crossover (20/100) | Guarded v1 | Out-of-sample | 94.00 | 30.85 | 0.45 | 16.60 | -5.00 | 3.32 | 1.54 | 1.66 | 19.00 | 108.27 |
| EMA Crossover (20/100) | Guarded v2 | 2012-2026 | 288.00 | 35.07 | 0.54 | 25.00 | -5.74 | 4.35 | 2.18 | 5.04 | 11.00 | 138.30 |
| EMA Crossover (20/100) | Guarded v2 | Out-of-sample | 92.00 | 34.78 | 0.53 | 15.54 | -5.52 | 2.81 | 1.55 | 1.80 | 10.00 | 118.02 |
| Donchian Breakout (55/20) | Raw | 2012-2026 | 351.00 | 42.17 | 0.73 | 12.66 | -5.68 | 2.23 | 1.55 | 2.05 | 10.00 | 76.55 |
| Donchian Breakout (55/20) | Raw | Out-of-sample | 107.00 | 39.25 | 0.65 | 10.12 | -5.15 | 1.97 | 1.24 | 0.85 | 9.00 | 71.01 |
| Donchian Breakout (55/20) | Guarded v1 | 2012-2026 | 348.00 | 38.22 | 0.62 | 12.68 | -5.48 | 2.31 | 1.42 | 1.46 | 16.00 | 65.49 |
| Donchian Breakout (55/20) | Guarded v1 | Out-of-sample | 106.00 | 36.79 | 0.58 | 10.41 | -4.75 | 2.19 | 1.35 | 0.83 | 9.00 | 63.62 |
| Donchian Breakout (55/20) | Guarded v2 | 2012-2026 | 350.00 | 41.71 | 0.72 | 12.76 | -5.66 | 2.26 | 1.56 | 2.03 | 10.00 | 76.45 |
| Donchian Breakout (55/20) | Guarded v2 | Out-of-sample | 106.00 | 38.68 | 0.63 | 10.20 | -5.18 | 1.97 | 1.28 | 0.77 | 9.00 | 70.74 |
| RSI-2 Mean Reversion | Raw | 2012-2026 | 1161.00 | 59.00 | 1.44 | 1.93 | -2.84 | 0.68 | 0.97 | -0.03 | 9.00 | 7.25 |
| RSI-2 Mean Reversion | Raw | Out-of-sample | 361.00 | 55.96 | 1.27 | 1.78 | -2.80 | 0.64 | 0.80 | -0.24 | 9.00 | 7.39 |
| RSI-2 Mean Reversion | Guarded v1 | 2012-2026 | 1095.00 | 58.45 | 1.41 | 1.89 | -2.90 | 0.65 | 0.87 | -0.10 | 10.00 | 6.80 |
| RSI-2 Mean Reversion | Guarded v1 | Out-of-sample | 354.00 | 55.93 | 1.27 | 1.76 | -2.78 | 0.63 | 0.81 | -0.24 | 10.00 | 6.75 |
| RSI-2 Mean Reversion | Guarded v2 | 2012-2026 | 1141.00 | 58.98 | 1.44 | 1.93 | -2.82 | 0.68 | 0.94 | -0.02 | 10.00 | 7.26 |
| RSI-2 Mean Reversion | Guarded v2 | Out-of-sample | 350.00 | 56.00 | 1.27 | 1.78 | -2.77 | 0.64 | 0.83 | -0.22 | 10.00 | 7.43 |

## 10. Calendar-year returns %

2026 is a partial year (to 2026-10-16).

| Year | EMA Raw | EMA v1 | EMA v2 | Donchian Raw | Donchian v1 | Donchian v2 | RSI-2 Raw | RSI-2 v1 | RSI-2 v2 | NIFTY 50 buy & hold |
|---|---|---|---|---|---|---|---|---|---|---|
| 2012 | 15.12 | 9.92 | 10.69 | 4.42 | -3.69 | 3.50 | 0.49 | 0.90 | 0.90 | 23.92 |
| 2013 | -11.15 | -9.03 | -4.43 | -2.77 | -2.71 | -2.61 | -4.04 | -4.47 | -4.50 | 6.76 |
| 2014 | 30.72 | 31.02 | 30.05 | 21.70 | 23.24 | 22.28 | -2.14 | -5.06 | -3.94 | 31.39 |
| 2015 | -5.80 | -7.49 | -5.93 | -5.44 | -4.96 | -5.47 | 0.27 | -4.10 | -1.53 | -4.06 |
| 2016 | 1.47 | 2.49 | 1.56 | -0.47 | -0.10 | 0.87 | 1.75 | 1.57 | 1.93 | 3.01 |
| 2017 | 26.37 | 34.41 | 34.81 | 8.98 | 12.15 | 11.35 | 3.45 | 3.69 | 4.13 | 28.65 |
| 2018 | 4.33 | 6.47 | 5.76 | 2.43 | 0.59 | 5.81 | -0.90 | -2.10 | -0.67 | 3.15 |
| 2019 | 9.19 | 0.86 | 1.06 | 1.97 | -2.50 | -0.76 | 1.44 | -3.75 | -0.34 | 12.02 |
| 2020 | 12.52 | 6.01 | 10.90 | 12.31 | 7.33 | 9.71 | -1.02 | -0.00 | -1.36 | 14.90 |
| 2021 | 23.61 | 16.33 | 19.06 | 9.97 | 6.46 | 8.17 | 5.20 | 6.78 | 6.19 | 24.12 |
| 2022 | 0.22 | -2.91 | -2.03 | -0.08 | 1.37 | 0.32 | -4.53 | -3.73 | -3.94 | 4.33 |
| 2023 | 13.55 | 11.07 | 10.23 | 6.77 | 7.62 | 7.08 | -1.54 | -2.53 | -2.63 | 20.03 |
| 2024 | 7.00 | 9.28 | 8.91 | 2.50 | 3.54 | 3.74 | 2.36 | 1.85 | 2.06 | 8.80 |
| 2025 | 8.04 | 9.41 | 12.12 | 2.37 | 3.13 | 3.05 | 1.63 | 1.38 | 2.90 | 10.51 |
| 2026 | -12.39 | -12.87 | -14.50 | -5.51 | -5.56 | -6.23 | -4.86 | -4.75 | -5.12 | -11.42 |

## 11. Risk profiles

Conservative / Balanced (= v1) / Aggressive were set by hand before testing (see `risk.py` PROFILES), not tuned on the data.

| Strategy | profile | CAGR % 2012-2026 | Max DD % 2012-2026 | Avg exposure % | CAGR % out-of-sample | Max DD % out-of-sample |
|---|---|---|---|---|---|---|
| EMA Crossover (20/100) | No rules | 7.59 | -18.33 | 69.50 | 2.77 | -14.81 |
| EMA Crossover (20/100) | Conservative | 4.39 | -16.98 | 48.08 | 1.80 | -11.26 |
| EMA Crossover (20/100) | Balanced | 6.35 | -18.45 | 62.04 | 2.24 | -14.54 |
| EMA Crossover (20/100) | Aggressive | 8.71 | -19.17 | 75.31 | 2.29 | -17.14 |
| Donchian Breakout (55/20) | No rules | 3.77 | -14.13 | 44.07 | 1.13 | -10.59 |
| Donchian Breakout (55/20) | Conservative | 2.39 | -10.66 | 29.27 | 1.87 | -8.80 |
| Donchian Breakout (55/20) | Balanced | 2.85 | -13.98 | 39.02 | 2.00 | -9.95 |
| Donchian Breakout (55/20) | Aggressive | 3.77 | -17.75 | 52.10 | 0.99 | -13.50 |
| RSI-2 Mean Reversion | No rules | -0.21 | -10.29 | 12.84 | -1.50 | -8.98 |
| RSI-2 Mean Reversion | Conservative | -1.03 | -16.40 | 8.76 | -1.24 | -7.35 |
| RSI-2 Mean Reversion | Balanced | -1.03 | -16.34 | 12.78 | -1.66 | -8.83 |
| RSI-2 Mean Reversion | Aggressive | -0.58 | -13.77 | 17.28 | -2.01 | -12.15 |

## Limitations

- Survivorship bias: the universe is today's large caps, tested back to 2012.
- Dividends: stock prices are dividend-adjusted (total return) but the NIFTY 50 benchmark (^NSEI) is a price index, so comparisons with NIFTY favour the strategies by roughly its dividend yield (about 1.2-1.5% a year).
- Uninvested cash earns nothing, while Sharpe subtracts a 6.5% risk-free rate; this understates partly-invested strategies.
- Daily bars: the daily-loss rule acts at the next open, not intraday. Intraday enforcement needs tick or minute data.
- Stops fill at the stop price unless the open gaps through it; real slippage in fast markets can be worse.
- Yahoo Finance data is unofficial; corporate-action adjustments can contain errors.
- Long-only, cash segment. F&O (where SEBI found most retail losses) is the natural next step.
