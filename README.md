# AlgoGuard

A rule-based algorithmic trading engine for NSE equities with an enforceable risk layer.

**Live dashboard: https://algoguard.streamlit.app** (on the web, the commitment lock lasts for your browser session).

Research question: **does a pre-committed, automatically enforced risk layer reduce tail risk (max drawdown, worst days, loss clusters) for common retail strategies, and what does it cost in returns?**

This grows out of last semester's TradeGuardian idea. A third-party app cannot stop a person from placing a manual trade in their broker's app. But when an algorithm places the orders, the risk engine sits in the execution path, so enforcement is real. That is the pivot.

## Verify every result in one command (for assessors)

```
pip install -r requirements.txt
python verify.py
```

`verify.py` checks the 67 bundled data files against `data/MANIFEST.sha256`, runs the 32 unit tests, re-runs both studies into a temporary folder and compares all 45 result files cell by cell with `results/`. Expected last line: `VERDICT: ALL RESULTS REPRODUCED` (about 90 seconds, offline). Do not run `--download` first: Yahoo revises adjusted prices over time, so fresh data moves the numbers slightly (a data difference, which the manifest check reports). Full write-up: `AlgoGuard_VolSelect_Review_Report.pdf` (architecture, results, win/loss, commercial viability).

## Run it (Windows, Anaconda/Miniconda Prompt)

```
cd algoguard
conda create -n algoguard python=3.11 -y
conda activate algoguard
pip install -r requirements.txt
python -m pytest -q tests          # 32 tests incl. no look-ahead, the commitment lock and the dashboard
python run.py                      # all experiments -> results\
python paper_trade.py --days 60    # paper-trading replay through the broker layer
streamlit run app.py               # live dashboard for the demo
```

The data used for every result is bundled in `data/`; `python run.py --download --force` fetches fresh data. Or double-click `run_all.bat` from an Anaconda Prompt (installs, verifies, opens the dashboard). Offline? Add `--demo` to `run.py` / `paper_trade.py` to use synthetic data (pipeline test only, not market results).

Everything runs on a normal laptop CPU in well under a minute. No GPU needed.

## What is inside

| Module | Purpose |
|---|---|
| `algoguard/data.py` | NSE daily OHLCV, NIFTY 50 and India VIX via yfinance, cached to CSV |
| `algoguard/strategies.py` | EMA crossover (trend), Donchian breakout (momentum), RSI-2 (mean reversion). Long-only |
| `algoguard/risk.py` | The guardrail engine: ATR stops, daily loss limit, losing-streak cooldown, drawdown circuit breaker, India VIX filter, volatility-scaled sizing. Every intervention logged with its reason |
| `algoguard/backtest.py` | Event-driven daily portfolio backtester. Signals at close, fills at next open, stops intraday, 0.15% cost per side |
| `algoguard/v2.py` | Guarded v2: per-strategy guardrail settings chosen from a 16-setting menu on pre-2022 data only, then tested once on 2022+; plus a yearly walk-forward |
| `algoguard/commitment.py` | Commitment lock: tightening a rule applies at once, loosening waits (1 h / 24 h / 7 days); turning the lock off or shortening the wait also waits. State saved in `rules_lock.json` |
| `algoguard/explain.py` | Plain-English explanation of any trading day: what was bought or sold and which rule stepped in |
| `algoguard/scanner.py` | Volatility scanner: stocks that got calmer while India VIX rose, on any date |
| `algoguard/metrics.py` | CAGR, Sharpe, Sortino, max drawdown, Calmar, worst day, VaR; trade statistics (win rate, win/loss ratio, payoff, profit factor, expectancy, losing streaks, holding period); calendar-year returns |
| `algoguard/broker.py` | Execution layer built around SEBI's retail algo framework: 10 orders/s limiter, MPP-protected limit orders, daily login, strategy tags. SimBroker + Kite Connect mapping |
| `run.py` | Experiments: raw vs guarded, in/out-of-sample, ablation, parameter grid, cost sensitivity, intervention counts, v2 (7), walk-forward (8), trade statistics (9), calendar-year returns (10), risk profiles (11) |
| `verify.py` | Independent re-run check: data manifest, tests, both studies, every result table compared |
| `app.py` | Streamlit dashboard: start from a risk profile (Conservative / Balanced / Aggressive) or v2, toggle each rule, commitment lock, before-vs-after-2022 check, explain-a-day, volatility scanner, 3-question profile quiz, audit log |
| `paper_trade.py` | Day-by-day replay through the broker layer |
| `tests/` | 32 tests: no look-ahead (engine, features, regime forecast, portfolio), rules fire, costs bite, no leverage, rate limiter, MPP pricing, commitment lock, trade statistics, both dashboard pages render |

## Outputs (`results/`)

`report.md` (all tables), `chart_1_equity_drawdown.png`, `chart_2_ablation.png`, `chart_3_robustness_grid.png`, `chart_4_v2_drawdown.png`, per-strategy trade lists and audit logs as CSV, and the v2 files: `7_v2_comparison.csv`, `7_v2_candidates_in_sample.csv`, `7_v2_chosen_settings.txt/.json` (the dashboard reads the .json for its v2 preset), `8_walk_forward*.csv`, `9_trade_stats.csv`, `10_calendar_returns.csv`, `11_risk_profiles.csv`. VolSelect adds `results/vs/win_loss.csv`, `calendar_returns.csv`, `cost_sensitivity.csv`, `overfitting_ic.csv`, `overfitting_auc.csv`.

## Design choices worth defending

- **No look-ahead**: decisions for day t use data up to close of t-1; tested by perturbing future prices.
- **Parameters fixed before testing** (textbook values), with a 2022+ hold-out period, so results are not curve-fitted.
- **Ablation** shows which rule actually does the work instead of claiming the whole bundle helps.
- **Realistic costs**: STT 0.1% per side on delivery is the dominant cost in Indian equities.

## Limitations

Survivorship bias (today's large caps), daily bars only, unofficial Yahoo data (placeholder bars are dropped on loading), dividends in stock prices but not in the NIFTY benchmark, long-only cash segment. See the end of `results/report.md`.

## Review report

`AlgoGuard_VolSelect_Review_Report.pdf`: architecture, verified results, win/loss statistics, commercial viability and every correction to the October results. Built from the result files by `python report/build_report.py`, which checks each claim against them.

## Extension: volatility-aware NIFTY 50 stock selection (academic research prototype, not investment advice)

When NIFTY volatility is expected to rise, which NIFTY 50 stocks hold up? A walk-forward study (2016–2026, hold-out 2022+):

| Module | Purpose |
|---|---|
| `algoguard/universe.py` | All 50 current NIFTY 50 stocks (NSE list with sectors), NIFTY and India VIX, cached in `data/nifty50/` |
| `algoguard/regime.py` | Probability of high volatility over the next 10 days (VIX, realised vol, GARCH(1,1)); calm / rising / high; accuracy vs a naive baseline |
| `algoguard/features.py` | 19 per-stock features: beta, downside beta, past high-vol excess return, sector, relative strength, liquidity, RSI, MACD, ADX, %B, ATR, OBV, stochastic, MA distance, momentum, volatility |
| `algoguard/selection.py` | Logistic regression (and gradient boosting) per regime; feature importance; information coefficients |
| `algoguard/portfolio.py` | Weekly top-10, inverse-vol weights; drawdown trigger that re-evaluates and switches approach, never goes to cash |
| `run_vs.py` | Runs everything, writes `results/vs/` (tables, 5 charts, audit log, report.md, current ranking) |
| `pages/2_Volatility_Selection.py` | Dashboard page: current regime, ranked stocks with reasons, equity vs benchmarks, drawdown, audit log |

```
python run_vs.py --download   # first time
python run_vs.py
```

Headline (walk-forward 2016–2026, regime switch without trigger): 17.0% a year against 10.4% for NIFTY buy and hold and 20.3% for equal-weight NIFTY 50. It lost less than both benchmarks in the COVID crash (−11.5% vs −18.6% and −19.4%) and in the 2022 sell-off, but from 2022 it trails equal weight even before costs (14.5% vs 15.4% a year), so there is no proven selection edge yet. Stock prices include dividends while NIFTY (^NSEI) does not, and survivorship bias flatters every approach here. Full results: `results/vs/report.md` and the review report.
