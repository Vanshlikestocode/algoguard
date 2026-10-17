# AlgoGuard results

Data: NSE daily data via Yahoo Finance. 12 stocks, 2012-01-02 to 2026-10-16, 3649 sessions. Capital Rs 10 lakh, costs 0.15% per side, signals at close, fills next open.

## 1. Raw strategy vs strategy + guardrails

| Strategy | risk layer | CAGR % | Sharpe | Max drawdown % | Worst day % | Days below -2% (count) | Calmar | Trades | Avg exposure % |
|---|---|---|---|---|---|---|---|---|---|
| EMA Crossover (20/100) | Raw | 7.55 | 0.14 | -18.33 | -6.89 | 27.00 | 0.41 | 291.00 | 69.70 |
| EMA Crossover (20/100) | Guarded | 6.79 | 0.07 | -23.56 | -7.24 | 20.00 | 0.29 | 359.00 | 66.66 |
| Donchian Breakout (55/20) | Raw | 3.78 | -0.32 | -14.13 | -5.28 | 8.00 | 0.27 | 351.00 | 44.06 |
| Donchian Breakout (55/20) | Guarded | 3.08 | -0.41 | -14.75 | -7.58 | 6.00 | 0.21 | 418.00 | 43.96 |
| RSI-2 Mean Reversion | Raw | -0.17 | -1.74 | -10.26 | -2.71 | 1.00 | -0.02 | 1163.00 | 12.85 |
| RSI-2 Mean Reversion | Guarded | -1.03 | -1.96 | -16.60 | -2.02 | 1.00 | -0.06 | 1142.00 | 13.22 |
| NIFTY 50 buy & hold | 11.28 | 0.36 | -38.44 | -12.98 | 86.00 | 0.29 | nan | nan |

## 2. In-sample vs out-of-sample (split 2022-01-01)

All parameters are textbook defaults fixed before testing, so the out-of-sample period is a genuine hold-out.

| Strategy | layer | period | CAGR % | Sharpe | Max drawdown % | Worst day % |
|---|---|---|---|---|---|---|
| EMA Crossover (20/100) | Raw | In-sample | 9.77 | 0.32 | -18.33 | -5.17 |
| EMA Crossover (20/100) | Raw | Out-of-sample | 2.81 | -0.32 | -14.81 | -6.89 |
| EMA Crossover (20/100) | Guarded | In-sample | 8.36 | 0.22 | -23.56 | -4.33 |
| EMA Crossover (20/100) | Guarded | Out-of-sample | 3.38 | -0.26 | -15.20 | -7.24 |
| Donchian Breakout (55/20) | Raw | In-sample | 5.04 | -0.14 | -14.13 | -3.16 |
| Donchian Breakout (55/20) | Raw | Out-of-sample | 1.15 | -0.80 | -10.52 | -5.28 |
| Donchian Breakout (55/20) | Guarded | In-sample | 3.87 | -0.29 | -14.75 | -7.58 |
| Donchian Breakout (55/20) | Guarded | Out-of-sample | 1.40 | -0.69 | -11.80 | -5.14 |
| RSI-2 Mean Reversion | Raw | In-sample | 0.47 | -1.51 | -7.82 | -1.56 |
| RSI-2 Mean Reversion | Raw | Out-of-sample | -1.49 | -2.29 | -8.96 | -2.71 |
| RSI-2 Mean Reversion | Guarded | In-sample | -0.64 | -1.88 | -16.60 | -1.94 |
| RSI-2 Mean Reversion | Guarded | Out-of-sample | -1.85 | -2.13 | -9.66 | -2.02 |

## 3. Ablation: contribution of each rule

Each rule switched on alone (vs raw), and each rule removed from the full set.

| Strategy | rule | Only this rule: Sharpe | Only this rule: Max DD % | Max DD change vs raw (pts) | All rules except this: Sharpe | All except this: Max DD % |
|---|---|---|---|---|---|---|
| EMA Crossover (20/100) | ATR stop-loss | 0.13 | -16.86 | 1.47 | 0.17 | -18.17 |
| EMA Crossover (20/100) | Daily loss limit | 0.14 | -18.33 | 0.00 | 0.04 | -24.02 |
| EMA Crossover (20/100) | Losing-streak cooldown | 0.13 | -18.15 | 0.18 | 0.06 | -25.05 |
| EMA Crossover (20/100) | Drawdown circuit breaker | 0.09 | -19.70 | -1.37 | 0.12 | -17.71 |
| EMA Crossover (20/100) | India VIX filter | 0.10 | -19.04 | -0.71 | 0.13 | -21.76 |
| EMA Crossover (20/100) | Volatility sizing | 0.19 | -16.95 | 1.38 | 0.10 | -17.06 |
| Donchian Breakout (55/20) | ATR stop-loss | -0.44 | -15.11 | -0.98 | -0.32 | -13.66 |
| Donchian Breakout (55/20) | Daily loss limit | -0.32 | -14.13 | 0.00 | -0.41 | -14.75 |
| Donchian Breakout (55/20) | Losing-streak cooldown | -0.32 | -14.13 | 0.00 | -0.43 | -14.93 |
| Donchian Breakout (55/20) | Drawdown circuit breaker | -0.32 | -14.13 | 0.00 | -0.41 | -14.75 |
| Donchian Breakout (55/20) | India VIX filter | -0.34 | -14.13 | -0.00 | -0.40 | -14.79 |
| Donchian Breakout (55/20) | Volatility sizing | -0.31 | -13.64 | 0.49 | -0.44 | -14.97 |
| RSI-2 Mean Reversion | ATR stop-loss | -1.86 | -12.47 | -2.21 | -1.81 | -12.11 |
| RSI-2 Mean Reversion | Daily loss limit | -1.74 | -10.26 | 0.00 | -1.96 | -16.60 |
| RSI-2 Mean Reversion | Losing-streak cooldown | -1.75 | -10.36 | -0.10 | -1.93 | -17.29 |
| RSI-2 Mean Reversion | Drawdown circuit breaker | -1.74 | -10.26 | 0.00 | -1.96 | -16.58 |
| RSI-2 Mean Reversion | India VIX filter | -1.86 | -9.98 | 0.28 | -1.90 | -15.02 |
| RSI-2 Mean Reversion | Volatility sizing | -1.70 | -10.84 | -0.58 | -2.01 | -12.08 |

## 4. Parameter robustness (EMA crossover, 10 settings)

Guardrails should help across settings, not just at one lucky parameter choice.

| Across 10 EMA settings | Raw Sharpe | Raw MaxDD % | Guarded Sharpe | Guarded MaxDD % |
|---|---|---|---|---|
| mean | 0.15 | -20.17 | 0.11 | -17.89 |
| min | 0.03 | -27.99 | -0.06 | -23.56 |
| max | 0.22 | -15.68 | 0.24 | -15.11 |

## 5. Transaction-cost sensitivity

| Strategy | layer | cost per side | CAGR % | Sharpe | Max drawdown % |
|---|---|---|---|---|---|
| EMA Crossover (20/100) | Raw | 0.05% | 7.90 | 0.17 | -17.82 |
| EMA Crossover (20/100) | Guarded | 0.05% | 7.66 | 0.15 | -17.64 |
| EMA Crossover (20/100) | Raw | 0.15% | 7.55 | 0.14 | -18.33 |
| EMA Crossover (20/100) | Guarded | 0.15% | 6.79 | 0.07 | -23.56 |
| EMA Crossover (20/100) | Raw | 0.30% | 7.06 | 0.10 | -19.02 |
| EMA Crossover (20/100) | Guarded | 0.30% | 6.55 | 0.05 | -21.88 |
| Donchian Breakout (55/20) | Raw | 0.05% | 4.19 | -0.26 | -13.76 |
| Donchian Breakout (55/20) | Guarded | 0.05% | 3.55 | -0.35 | -14.24 |
| Donchian Breakout (55/20) | Raw | 0.15% | 3.78 | -0.32 | -14.13 |
| Donchian Breakout (55/20) | Guarded | 0.15% | 3.08 | -0.41 | -14.75 |
| Donchian Breakout (55/20) | Raw | 0.30% | 3.17 | -0.39 | -14.71 |
| Donchian Breakout (55/20) | Guarded | 0.30% | 1.99 | -0.55 | -17.60 |
| RSI-2 Mean Reversion | Raw | 0.05% | 1.14 | -1.39 | -7.46 |
| RSI-2 Mean Reversion | Guarded | 0.05% | 0.39 | -1.58 | -11.56 |
| RSI-2 Mean Reversion | Raw | 0.15% | -0.17 | -1.74 | -10.26 |
| RSI-2 Mean Reversion | Guarded | 0.15% | -1.03 | -1.96 | -16.60 |
| RSI-2 Mean Reversion | Raw | 0.30% | -2.10 | -2.26 | -27.47 |
| RSI-2 Mean Reversion | Guarded | 0.30% | -3.26 | -2.59 | -39.51 |

## 6. How often the guardrails intervened

Every intervention is in the audit log CSVs (date, rule, action, detail).

| Strategy | ATR stops hit | Halts (drawdown) | Daily-loss cooldowns | Losing-streak pauses | Entries blocked: India VIX filter | Entries blocked: Daily loss limit | Entries blocked: Losing-streak cooldown | Entries blocked: Drawdown circuit breaker |
|---|---|---|---|---|---|---|---|---|
| EMA Crossover (20/100) | 100 | 4 | 20 | 56 | 312 | 23 | 129 | 307 |
| Donchian Breakout (55/20) | 120 | 0 | 6 | 57 | 221 | 24 | 148 | 0 |
| RSI-2 Mean Reversion | 91 | 1 | 1 | 64 | 140 | 0 | 269 | 15 |

## 7. Guarded v2: strategy-aware guardrails

Each strategy picks its own drawdown-breaker mode, VIX filter and stop distance from a fixed menu of 16 settings. The choice is made by highest Calmar on data before 2022-01-01 only, then run once on the out-of-sample period. All other rules are unchanged from v1.

Chosen settings:

- EMA Crossover (20/100): breaker: sell all, VIX filter: off, stop: none
- Donchian Breakout (55/20): breaker: sell all, VIX filter: off, stop: none
- RSI-2 Mean Reversion: breaker: sell all, VIX filter: off, stop: none

| Strategy | layer | period | CAGR % | Sharpe | Max drawdown % | Worst day % | Days below -2% (count) | Calmar |
|---|---|---|---|---|---|---|---|---|
| EMA Crossover (20/100) | Raw | In-sample | 9.77 | 0.32 | -18.33 | -5.17 | 22.00 | 0.53 |
| EMA Crossover (20/100) | Raw | Out-of-sample | 2.81 | -0.32 | -14.81 | -6.89 | 5.00 | 0.19 |
| EMA Crossover (20/100) | Guarded v1 | In-sample | 8.36 | 0.22 | -23.56 | -4.33 | 15.00 | 0.36 |
| EMA Crossover (20/100) | Guarded v1 | Out-of-sample | 3.38 | -0.26 | -15.20 | -7.24 | 5.00 | 0.22 |
| EMA Crossover (20/100) | Guarded v2 | In-sample | 9.83 | 0.35 | -16.71 | -4.61 | 15.00 | 0.59 |
| EMA Crossover (20/100) | Guarded v2 | Out-of-sample | 4.79 | -0.11 | -15.10 | -7.24 | 7.00 | 0.32 |
| Donchian Breakout (55/20) | Raw | In-sample | 5.04 | -0.14 | -14.13 | -3.16 | 7.00 | 0.36 |
| Donchian Breakout (55/20) | Raw | Out-of-sample | 1.15 | -0.80 | -10.52 | -5.28 | 1.00 | 0.11 |
| Donchian Breakout (55/20) | Guarded v1 | In-sample | 3.87 | -0.29 | -14.75 | -7.58 | 5.00 | 0.26 |
| Donchian Breakout (55/20) | Guarded v1 | Out-of-sample | 1.40 | -0.69 | -11.80 | -5.14 | 1.00 | 0.12 |
| Donchian Breakout (55/20) | Guarded v2 | In-sample | 5.04 | -0.16 | -13.64 | -2.41 | 4.00 | 0.37 |
| Donchian Breakout (55/20) | Guarded v2 | Out-of-sample | 1.67 | -0.63 | -11.71 | -5.29 | 1.00 | 0.14 |
| RSI-2 Mean Reversion | Raw | In-sample | 0.47 | -1.51 | -7.82 | -1.56 | 0.00 | 0.06 |
| RSI-2 Mean Reversion | Raw | Out-of-sample | -1.49 | -2.29 | -8.96 | -2.71 | 1.00 | -0.17 |
| RSI-2 Mean Reversion | Guarded v1 | In-sample | -0.64 | -1.88 | -16.60 | -1.94 | 0.00 | -0.04 |
| RSI-2 Mean Reversion | Guarded v1 | Out-of-sample | -1.85 | -2.13 | -9.66 | -2.02 | 1.00 | -0.19 |
| RSI-2 Mean Reversion | Guarded v2 | In-sample | 0.08 | -1.59 | -10.73 | -1.89 | 0.00 | 0.01 |
| RSI-2 Mean Reversion | Guarded v2 | Out-of-sample | -1.46 | -1.96 | -9.59 | -2.42 | 1.00 | -0.15 |
| NIFTY 50 buy & hold | In-sample | 13.80 | 0.48 | -38.44 | -12.98 | 66.00 | 0.36 |
| NIFTY 50 buy & hold | Out-of-sample | 5.86 | 0.02 | -16.47 | -5.93 | 20.00 | 0.36 |

Every candidate's in-sample score is in `7_v2_candidates_in_sample.csv`.

## Limitations

- Survivorship bias: the universe is today's large caps, tested back to 2012.
- Daily bars: the daily-loss rule acts at the next open, not intraday. Intraday enforcement needs tick or minute data.
- Stops fill at the stop price unless the open gaps through it; real slippage in fast markets can be worse.
- Yahoo Finance data is unofficial; corporate-action adjustments can contain errors.
- Long-only, cash segment. F&O (where SEBI found most retail losses) is the natural next step.
