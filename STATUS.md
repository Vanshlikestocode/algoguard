# AlgoGuard: status after steps 1 to 5

Last updated: 17 Oct 2026. Replaces the status.md handover. Use `algoguard_v3.zip`.

## What got done

| Step | Status | Where |
|---|---|---|
| 1. Which rule causes the damage | Done | `results/report.md` section 3, notes below |
| 2. v2 strategy-aware guardrails | Done, chosen on pre-2022 data, tested once on 2022+ | `algoguard/v2.py`, `run.py` section 7, `results/7_*` |
| 3. Dashboard check | Done. New "Start from: v1 / v2" switch and a "breaker sells everything" checkbox | `app.py` |
| 4. Paper trading | Done: 60 sessions, 11 orders, 11 filled, 0 rejected, ended Rs 9,95,787 | `paper_orders.csv` |
| 5. Deck | Done, 18 slides with speaker notes | Claude artifact link (see the chat) |
| Extra: risk profiles, commitment lock, before/after-2022 tab | Done, 16 tests pass, checked in the dashboard | `risk.py` PROFILES, `algoguard/commitment.py`, `app.py`, deck slides 13-14 |
| 6. Rehearse with Q&A | Still to do, by both of us | `REVIEW_GUIDE.md` (3 new v2 questions added) |

Data was re-downloaded on 17 Oct 2026 and the main table matches the old status.md exactly (2 Jan 2012 to 16 Oct 2026, 3,649 sessions). Data CSVs are inside the zip, so nothing needs internet on the day.

## Step 1 findings (ablation)

Change in max drawdown when one rule is added alone to the raw strategy (points, plus = shallower):

| Rule | EMA | Donchian | RSI-2 |
|---|---|---|---|
| ATR stop-loss | +1.47 | -0.98 | -2.21 |
| Daily loss limit | 0.00 | 0.00 | 0.00 |
| Losing-streak cooldown | +0.18 | 0.00 | -0.10 |
| Drawdown breaker | -1.37 | 0.00 | 0.00 |
| India VIX filter | -0.71 | 0.00 | +0.28 |
| Volatility sizing | +1.38 | +0.49 | -0.58 |
| All six together | -5.23 | -0.62 | -6.34 |

- Breaker whipsaw: confirmed on EMA. 19 Feb 2019 it sold everything at -15.1%; NIFTY went 10,604 to 11,521 during the 20-session halt. On restart it resets its peak lower, so the 2020 fall never triggered it. Worst stretch -23.6%, Aug 2018 to Sep 2020.
- ATR stops: confirmed for Donchian and RSI-2 (they already have exit signals). On EMA the stop alone helps.
- VIX filter hurting RSI-2: not confirmed on the full period (+0.28 alone). On pre-2022 data alone it did hurt (-1.05).
- The big one: single-rule effects are small, but together they cost 5 to 6 points. The rules interact.
- The worst drawdown of every strategy happened before 2022, so in-sample data is where the damage is.

## Step 2: v2 result

Menu (fixed first): breaker sells all / blocks entries only; VIX filter on / off; ATR stop 3x / 4x / 5x / none. 16 settings. Chosen by best in-sample Calmar on data cut at 31 Dec 2021.

All three strategies chose the same: VIX filter off, no ATR stop, breaker unchanged (sell all). Our "block entries only" idea did not win anywhere.

Out-of-sample (2022 onward):

| Strategy | Raw CAGR / DD | v1 CAGR / DD | v2 CAGR / DD |
|---|---|---|---|
| EMA | 2.81 / -14.81 | 3.38 / -15.20 | 4.79 / -15.10 |
| Donchian | 1.15 / -10.52 | 1.40 / -11.80 | 1.67 / -11.71 |
| RSI-2 | -1.49 / -8.96 | -1.85 / -9.66 | -1.46 / -9.59 |

v2 beat v1 on all three and raw on return for EMA and Donchian, but drawdown stayed 0.3 to 1.2 points deeper than raw. Present it as that: strategy-aware rules won back the return v1 gave away; cutting tail risk out of sample is still open.

## Risk profiles (EMA crossover)

| Profile | 2012-26 CAGR / DD | 2022+ CAGR / DD |
|---|---|---|
| No rules | 7.55 / -18.33 | 2.81 / -14.81 |
| Conservative | 5.81 / -15.68 | 3.22 / -12.48 |
| Balanced (v1) | 6.79 / -23.56 | 3.38 / -15.20 |
| Aggressive | 7.79 / -19.35 | 2.45 / -17.08 |

From 2022, Conservative also beat raw on drawdown for Donchian (-10.19 vs -10.52) and RSI-2 (-7.66 vs -8.96). Mostly from holding less (57% vs 70% invested on EMA). Profiles were set by hand before testing.

## Code changes in this version

- `risk.py`: `dd_flatten` flag (False = breaker only blocks new entries, logged as "HALT").
- `algoguard/v2.py`: the menu, selection on truncated in-sample data, tie goes to the setting closest to v1.
- `run.py`: section 7 (v2), `chart_4_v2_drawdown.png`, v2 CSV/TXT/JSON outputs; fixed broken markdown tables in report.md; halt count includes block-only halts.
- `app.py`: v1/v2 preset switch, breaker mode checkbox, halt markers for both modes.
- `tests/`: 8th test, the block-only breaker never force-sells.

## Before the review

- Live dashboard: https://algoguard.streamlit.app (repo is public; Streamlit redeploys on every push to main). Open it a few minutes early in case it has gone to sleep.

- Delete `rules_lock.json` (if it exists) so the dashboard starts unlocked.
- On the Windows laptop: extract `algoguard_v3.zip` into `C:\Projects` (it contains the `algoguard` folder), then `python -m pytest -q tests`, `python run.py`, `streamlit run app.py`. No `--download` needed; data is included.
- Rehearse the 2-minute demo on slide 16 (its speaker notes have the clicks).
- Share the deck link with your partner from the deck's Share menu; it is private until shared.
