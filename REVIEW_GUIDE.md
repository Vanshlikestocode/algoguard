# Review guide (10-minute slot)

## Before the review
1. Run `python run.py` on real data. Open `results/report.md` and the three charts.
2. Fill in the real numbers below from `1_main_comparison.csv` and `3_ablation.csv`.
3. Have `streamlit run app.py` open and tested on the laptop you will present from.

## Story (what to say)
1. **What changed since last sem (1 min).** Last time we pitched a business. The feedback was fair: no algorithm, and the core promise (blocking a trader's manual orders) is not technically possible through broker APIs. So we moved the guardrail to where enforcement is real: inside an algo's execution path.
2. **Research question (30 s).** Does an automatically enforced risk layer reduce tail risk for common retail strategies, and what does it cost in return?
3. **System (1.5 min).** Data -> strategies -> risk engine -> backtester/paper broker. Show the module table in README. Point out: no look-ahead (and the test that proves it), real Indian costs, SEBI algo framework constraints in the broker layer.
4. **Results (3 min).** Chart 1 (raw vs guarded equity and drawdown). Then the ablation chart: which rule actually helped. Then the robustness grid: is it consistent across parameters, or one lucky setting? Quote the out-of-sample numbers, not just the full period.
5. **Live demo (2 min).** In the dashboard switch off all guardrails, then turn on only the VIX filter or drawdown breaker, zoom into Feb–Apr 2020, open the audit log to show the exact days it blocked trades.
6. **Limitations and next steps (1 min).** See below.

Whatever the results show, report them straight. "The guardrails cut max drawdown by X points but cost Y% CAGR" or even "rule Z did not help and here is why" is a research finding. Overclaiming is what an industry external will punish.

## Questions the external is likely to ask
- **"Isn't this overfitted?"** Parameters are textbook defaults chosen before testing; hold-out from 2022; robustness grid across 10 EMA settings; ablation per rule.
- **"Isn't v2 curve-fitted?"** The menu (16 settings) and the scoring rule (best Calmar) were fixed first; the data was cut at 31 Dec 2021 before scoring; 2022 onward was run once. Every candidate's in-sample score is in `results/7_v2_candidates_in_sample.csv`. Four years is still a short hold-out, so we say so.
- **"You only tested once (one hold-out)."** We also ran a walk-forward: every 1 January the v2 setting is re-picked using only earlier data, then used for that year, 2015 to 2026. EMA: 7.00% CAGR / -18.2% max DD, against 6.88% / -16.8% with no rules and 5.66% / -23.6% for v1. Donchian beat no rules on both (2.96% / -13.7% vs 2.90% / -14.1%). So v2 is not a one-off, but it roughly ties no rules rather than clearly beating them.
- **"So do the guardrails work?"** v1 (generic rules) cost return and deepened max drawdown. v2 (VIX filter and ATR stop off) beat v1 out of sample on all three strategies and beat raw on return for EMA and Donchian, but drawdown stayed 0.3 to 1.2 points deeper than raw. We have not shown a risk layer that cuts tail risk out of sample.
- **"What if a trader wants different limits?"** Three starting profiles (Conservative, Balanced = v1, Aggressive), hand-picked before testing; every rule is still adjustable. From 2022, Conservative cut drawdown below raw on all three strategies (EMA -12.5% vs -14.8%), mostly by holding less (57% vs 70% invested); over 2012-2026 it earned less (5.8% vs 7.6% CAGR on EMA).
- **"Can't the trader just switch the rules off after a bad day?"** Not inside AlgoGuard: the commitment lock applies tightening at once but queues any loosening (including switching the lock off) for the chosen waiting period. It cannot stop someone trading by hand in their own broker app.
- **"Why did the drawdown breaker hurt?"** 19 Feb 2019: EMA hit -15.1%, the breaker sold everything; NIFTY rose from 10,604 to 11,521 during the 20-session halt. On restart the peak resets lower, so the 2020 fall did not trigger it. Worst stretch -23.6% (Aug 2018 to Sep 2020).
- **"Look-ahead bias?"** Signals at close t, fills at open t+1; unit test changes future prices and asserts the past equity is identical.
- **"Survivorship bias?"** Yes, the universe is today's large caps. Fix: point-in-time NIFTY 50 constituents. Stated in limitations.
- **"Costs?"** 0.15% per side (STT 0.1% delivery + charges + slippage); cost-sensitivity table at 0.05/0.15/0.30%.
- **"Can this go live?"** Broker layer already respects the SEBI retail algo framework (static IP, daily login, 10 orders/s, MPP-protected orders, strategy tags). Live use needs a broker-empanelled setup and strategy registration via the broker.
- **"Why not machine learning?"** First establish an honest baseline and evaluation harness. ML signals can plug into the same engine and be judged by the same tests; most published ML trading results fail exactly these checks.
- **"Daily bars for a daily loss limit?"** Correct limitation: acts at next open. Intraday version needs minute data, which is the next step.

## Next steps (for the roadmap slide)
1. Intraday version on minute data (true intraday loss limits).
2. Point-in-time index constituents to remove survivorship bias.
3. Walk-forward optimisation of risk thresholds.
4. F&O: options strategies, where SEBI found the bulk of retail losses.
5. Broker-empanelled paper trading with live feed.
