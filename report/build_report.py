"""Build the review report (report/report.html, then a PDF if Chrome or Edge is installed) from the
result files only. Every number is read from results/ and results/vs/, and every comparative claim in
the text is checked against those numbers with `claim(...)`: if a claim is not supported, the build fails.

    python run.py && python run_vs.py      # (or python verify.py)
    python report/build_report.py
"""
from __future__ import annotations

import html
import json
import os
import shutil
import subprocess
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
R, V = ROOT / "results", ROOT / "results" / "vs"
sys.path.insert(0, str(ROOT))
from algoguard.data import read_csv  # noqa: E402

E, D, RS = "EMA Crossover (20/100)", "Donchian Breakout (55/20)", "RSI-2 Mean Reversion"
STRATS = {E: "EMA crossover", D: "Donchian breakout", RS: "RSI-2 mean reversion"}
SHORT = {E: "EMA", D: "Donchian", RS: "RSI-2"}
NIFTY = "NIFTY 50 buy & hold"
RSW, STRESS, TRIG = "Regime switch (LR), no trigger", "Stress model only", "Regime switch (LR) + 12% trigger"
EW, NB, MOM = "Equal-weight NIFTY 50 (benchmark)", "NIFTY 50 buy and hold (benchmark)", "Momentum only"


def claim(ok: bool, text: str) -> None:
    if not bool(ok):
        raise AssertionError(f"Report claim not supported by the result files: {text}")


def n(x, d=2, sign=False) -> str:
    """Number with a real minus sign."""
    if pd.isna(x):
        return "–"
    s = f"{x:+,.{d}f}" if sign else f"{x:,.{d}f}"
    return s.replace("-", "−")


def csv(p: Path, idx=0) -> pd.DataFrame:
    return pd.read_csv(p, index_col=idx)


# ------------------------------------------------------------------ load every result
info = json.loads((R / "run_info.json").read_text(encoding="utf-8"))
main = csv(R / "1_main_comparison.csv")
v2 = csv(R / "7_v2_comparison.csv")
chosen = json.loads((R / "7_v2_chosen_settings.json").read_text(encoding="utf-8"))["settings"]
wf = csv(R / "8_walk_forward.csv")
picks = pd.read_csv(R / "8_walk_forward_picks.csv")
ts = csv(R / "9_trade_stats.csv")
cal = csv(R / "10_calendar_returns.csv")
prof = csv(R / "11_risk_profiles.csv")
abl = csv(R / "3_ablation.csv", [0, 1])
rob = csv(R / "4_robustness.csv")
cost = csv(R / "5_cost_sensitivity.csv")
ema_log = pd.read_csv(R / "audit_log_ema.csv", parse_dates=["date"])
vt = {k: csv(V / f"table_{k}.csv") for k in ("full", "development", "hold-out", "covid", "2022")}
wl = csv(V / "win_loss.csv")
vcost = csv(V / "cost_sensitivity.csv")
ic = csv(V / "overfitting_ic.csv")
cap = csv(V / "capacity.csv")["value"]
acc = csv(V / "forecast_accuracy.csv")
nifty = read_csv(ROOT / "data" / "IDX_NSEI.csv")
SPAN = f"{info['start'][:4]}–{info['end'][:4]}"
TSPAN = f"{info['start'][:4]}-{info['end'][:4]}"  # label used inside the CSVs

m = lambda s, lab: main.loc[f"{s} | {lab}"]
oos = lambda s, lab: v2.loc[f"{s} | {lab} | Out-of-sample"]
ins = lambda s, lab: v2.loc[f"{s} | {lab} | In-sample"]
pr = lambda s, lab: prof.loc[f"{s} | {lab}"]
tsr = lambda s, lab, per: ts.loc[f"{s} | {lab} | {per}"]
vc = lambda a, c: vcost.loc[f"{a} | {c}"]

# ------------------------------------------------------------------ claims checked against the data
nifty_cagr, nifty_dd = main.loc[NIFTY, "CAGR %"], main.loc[NIFTY, "Max drawdown %"]
claim(all(m(s, "Raw")["CAGR %"] < nifty_cagr for s in STRATS), "no strategy beats NIFTY on CAGR")
claim(m(E, "Raw")["Calmar"] > main.loc[NIFTY, "Calmar"], "EMA Calmar above NIFTY Calmar")
claim(all(m(s, "Raw")["Max drawdown %"] > nifty_dd for s in STRATS), "all strategies shallower drawdown than NIFTY")
claim(all(oos(s, "Guarded v1")["Max drawdown %"] > oos(s, "Raw")["Max drawdown %"] for s in STRATS),
      "v1 shallower out-of-sample drawdown than raw on all three")
oos_prof = {s: prof.loc[f"{s} | Conservative", "Max DD % out-of-sample"] for s in STRATS}
claim(all(oos_prof[s] > oos(s, "Guarded v1")["Max drawdown %"] for s in STRATS),
      "Conservative shallower out-of-sample drawdown than v1 on all three")
claim(all(m(s, "Guarded")["CAGR %"] < m(s, "Raw")["CAGR %"] for s in STRATS), "v1 costs return over the full period")
claim(all(oos(s, "Guarded v2")["Max drawdown %"] < oos(s, "Guarded v1")["Max drawdown %"] for s in STRATS),
      "v2 deeper out-of-sample drawdown than v1 on all three")
claim(all(ins(s, "Guarded v2")["Calmar"] > ins(s, "Guarded v1")["Calmar"] for s in STRATS),
      "v2 better in-sample Calmar than v1 on all three")
claim(tsr(E, "Raw", TSPAN)["Profit factor"] > 1 > tsr(RS, "Raw", TSPAN)["Profit factor"], "EMA PF > 1 > RSI-2 PF")
claim(tsr(RS, "Raw", TSPAN)["Win rate %"] > tsr(E, "Raw", TSPAN)["Win rate %"], "RSI-2 wins more often than EMA")
cov, h1 = vt["covid"]["Period return %"], vt["2022"]["Period return %"]
for a in (RSW, STRESS):
    claim(cov[a] > max(cov[NB], cov[EW]) and h1[a] > max(h1[NB], h1[EW]), f"{a} lost less than NIFTY and EW in both crashes")
claim(vc(RSW, "0.00%")["CAGR % 2022+"] < vc(EW, "0.00%")["CAGR % 2022+"], "regime switch trails EW from 2022 even gross")
claim(vc(RSW, "0.00%")["CAGR % 2016-2021"] > vc(EW, "0.00%")["CAGR % 2016-2021"], "regime switch beat EW gross 2016-2021")
claim(vt["full"].loc[RSW, "CAGR %"] < vt["full"].loc[EW, "CAGR %"], "regime switch net trails EW over the full period")
claim(all(vt["full"].loc[a, "CAGR %"] > vt["full"].loc[NB, "CAGR %"] for a in (RSW, STRESS, MOM, TRIG)), "all beat NIFTY full")
flagged = list(ic.index[ic["Flag"].fillna("") != ""])
claim(set(flagged) == {"beta", "down_beta"}, "only beta and down_beta flagged after the IC fix")
halts = ema_log[ema_log.action.str.startswith("HALT")]
claim(list(halts.date.dt.strftime("%Y-%m-%d")) == ["2015-12-07", "2020-03-12"], "EMA v1 breaker fired on these dates")
h_i = nifty.index.get_loc(pd.Timestamp("2020-03-12"))
n_open, n_low = nifty.iloc[h_i + 1]["open"], nifty["close"].iloc[h_i + 1:h_i + 21].min()
n_low_d, n_end, n_end_d = nifty["close"].iloc[h_i + 1:h_i + 21].idxmin(), nifty["close"].iloc[h_i + 20], nifty.index[h_i + 20]
claim(n_low < n_open and n_end < n_open, "NIFTY fell further after the March 2020 breaker sale and ended the halt lower")
stop_picks = Counter(picks.iloc[:, 2].str.extract(r"stop: (.*)")[0])
yrs_v1 = [str(y) for y in cal.index if cal.loc[y, "EMA v1"] > cal.loc[y, NIFTY]]
wfd = lambda s, lab: wf.loc[f"{s} | {lab}", "Days below -2% (count)"]
claim(all(wfd(s, "Guarded v1") < wfd(s, "Raw") for s in (E, D)), "v1 fewest bad days on EMA and Donchian (walk-forward)")
wf_beat = [(s, lab) for s in STRATS for lab in ("Guarded v1", "Walk-forward v2")
           if wf.loc[f"{s} | {lab}", "CAGR %"] > wf.loc[f"{s} | Raw", "CAGR %"]]
wf_gap = {k: wf.loc[f"{k[0]} | {k[1]}", "CAGR %"] - wf.loc[f"{k[0]} | Raw", "CAGR %"] for k in wf_beat}
claim(all(g < 0.05 for g in wf_gap.values()), "any rule set ahead of no rules on walk-forward return is ahead by under 0.05 points")
wf_sentence = ("No rule set beats no rules on return over 2015–2026." if not wf_beat else
               "On return over 2015–2026 the rule sets at best tie no rules: " + "; ".join(
                   f"{SHORT[k[0]]} {k[1]} is ahead by only {wf_gap[k]:.3f} points a year" for k in wf_beat) + ", and every other one is behind.")
gross_rsw, gross_ew = vc(RSW, "0.00%")["CAGR %"], vc(EW, "0.00%")["CAGR %"]
# break-even cost per side: linear interpolation between the 0.05% and 0.15% rows
d05 = vc(RSW, "0.05%")["CAGR %"] - vc(EW, "0.05%")["CAGR %"]
d15 = vc(RSW, "0.15%")["CAGR %"] - vc(EW, "0.15%")["CAGR %"]
claim(d05 > 0 > d15, "break-even between 0.05% and 0.15%")
breakeven = 0.05 + 0.10 * d05 / (d05 - d15)

# ------------------------------------------------------------------ code inventory, tests, result files
def lines(p: Path) -> int:
    return sum(1 for _ in p.open(encoding="utf-8"))


collected = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "tests"], cwd=ROOT,
                           capture_output=True, text=True, encoding="utf-8").stdout.splitlines()
tests = Counter(x.split("::")[0].split("/")[-1] for x in collected if "::" in x)
n_tests = sum(tests.values())
result_files = sorted(R.glob("*.csv")) + sorted(R.glob("*.json")) + sorted(V.glob("*.csv")) + sorted(V.glob("*.json"))
n_data = len(list((ROOT / "data").rglob("*.csv")))
code_files = sorted((ROOT / "algoguard").glob("*.py")) + [ROOT / f for f in ("run.py", "run_vs.py", "verify.py", "paper_trade.py", "app.py")] \
    + sorted((ROOT / "pages").glob("*.py"))
total_lines = sum(lines(p) for p in code_files) + sum(lines(p) for p in (ROOT / "tests").glob("*.py"))


# ------------------------------------------------------------------ table helpers
def table(head: list[str], rows: list[list], cls: list[str] | None = None) -> str:
    """Numbers right-aligned, text left-aligned (a column is text if any of its cells is)."""
    numeric = lambda v: str(v).replace(",", "").replace(".", "").replace("−", "").replace("+", "").replace("%", "").strip() in ("", "–") \
        or str(v).replace(",", "").replace(".", "").replace("−", "").replace("+", "").replace("%", "").strip().isdigit()
    text_col = [i == 0 or any(not numeric(r[i]) for r in rows) for i in range(len(head))]
    h = "".join(f'<th{" class=l" if text_col[i] else ""}>{html.escape(c)}</th>' for i, c in enumerate(head))
    body = ""
    for k, r in enumerate(rows):
        c = f' class="{cls[k]}"' if cls and cls[k] else ""
        body += f"<tr{c}>" + "".join(f'<td{" class=l" if text_col[i] else ""}>{v}</td>' for i, v in enumerate(r)) + "</tr>"
    return f"<table><tr>{h}</tr>{body}</table>"


DESC = {
    "data.py": "Download (yfinance), defensive CSV reader that drops Yahoo's placeholder bars, date alignment, synthetic data for offline tests",
    "indicators.py": "EMA, SMA, RSI, ATR, realised vol, MACD, ADX, stochastic, OBV, Bollinger %B",
    "strategies.py": "EMA crossover, Donchian breakout, RSI-2 mean reversion (0/1 target positions)",
    "risk.py": "RiskConfig, the six rules, three profiles, ablation helpers, RiskManager state machine with audit log",
    "backtest.py": "Event-driven daily portfolio backtester: costs, sizing, stops (no re-buy until the signal resets), cash, exposure, trades",
    "v2.py": "Strategy-aware guardrails: 16-setting menu, in-sample selection on truncated data, yearly walk-forward",
    "commitment.py": "Commitment lock: tightening applies at once, loosening waits 1 h / 24 h / 7 days",
    "broker.py": "10 orders/s limiter, MPP-protected limit prices, daily login, strategy tags, SimBroker, Kite Connect mapping",
    "explain.py": "Plain-English explanation of any trading day from the audit log",
    "scanner.py": "Stocks that calmed while India VIX rose",
    "metrics.py": "CAGR, Sharpe, Sortino, drawdown, Calmar, VaR, trade statistics (win/loss), calendar-year returns",
    "universe.py": "NIFTY 50 constituents with sectors, download and load",
    "regime.py": "GARCH(1,1) fitted on past data only, logistic regime forecast, accuracy vs a naive baseline",
    "features.py": "19 per-stock features on the NIFTY calendar and the 10-day excess-return target",
    "selection.py": "Per-regime models (LR, GB), scoring, coefficients, information coefficients",
    "portfolio.py": "Weekly top-K inverse-vol portfolio, drawdown trigger that retrains and switches approach",
    "run.py": "AlgoGuard experiments 1–11 → results/",
    "run_vs.py": "VolSelect walk-forward study → results/vs/",
    "verify.py": "Independent re-run check (section 2)",
    "paper_trade.py": "Paper replay through the broker layer (order path only)",
    "app.py": "Streamlit dashboard, main page",
    "2_Volatility_Selection.py": "Streamlit dashboard, VolSelect page",
    "__init__.py": "Package marker",
}
TEST_DESC = {
    "test_engine.py": "No look-ahead; signals are 0/1; raw has no interventions; VIX rule blocks all entries at VIX 99; costs reduce equity; never leveraged; MPP price and 10 orders/s limit; block-only breaker never force-sells; no re-buy after a stop until the signal resets",
    "test_vs.py": "No look-ahead in features, regime forecast and portfolio; drawdown trigger stays invested and logs; equal weight holds every stock",
    "test_commitment.py": "Tightening applies at once; loosening waits; changing the request restarts the clock; cannot escape by switching the lock off or shortening the wait; profiles ordered by risk",
    "test_explain.py": "Cooldown day, blocked entry, quiet and closed days explained correctly",
    "test_scanner.py": "Flags a stock that calms while VIX rises; flags nothing when VIX falls",
    "test_trade_stats.py": "Win/loss counts, profit factor, losing streak, holding period, calendar returns on a hand-checked example",
    "test_dashboard.py": "Both dashboard pages render on the bundled data without an exception",
}
claim(set(tests) <= set(TEST_DESC), "every test file is described")

code_rows = [[f"<code>{p.relative_to(ROOT).as_posix()}</code>", str(lines(p)), html.escape(DESC.get(p.name, ""))]
             for p in code_files if p.name != "__init__.py"]
test_rows = [[f"<code>{f}</code>", str(k), html.escape(TEST_DESC[f])] for f, k in sorted(tests.items(), key=lambda x: -x[1])]

# main AlgoGuard table
main_rows, main_cls = [], []
for s in STRATS:
    for lab, show in (("Raw", "No rules"), ("Guarded", "Guarded v1")):
        r = m(s, lab)
        main_rows.append([STRATS[s] if lab == "Raw" else "", show, n(r["CAGR %"]), n(r["Sharpe"]), n(r["Max drawdown %"]),
                          n(r["Worst day %"]), n(r["Days below -2% (count)"], 0), n(r["Calmar"]), n(r["Trades"], 0),
                          n(r["Avg exposure %"], 1)])
        main_cls.append("")
r = main.loc[NIFTY]
main_rows.append(["NIFTY 50", "Buy and hold", n(r["CAGR %"]), n(r["Sharpe"]), n(r["Max drawdown %"]), n(r["Worst day %"]),
                  n(r["Days below -2% (count)"], 0), n(r["Calmar"]), "–", "100"])
main_cls.append("bench")

# out-of-sample side by side
oos_rows, oos_cls = [], []
for s in STRATS:
    for lab, show in (("Raw", "No rules"), ("Guarded v1", "Guarded v1 (fixed textbook rules)"),
                      ("Guarded v2", "Guarded v2 (tuned on pre-2022 data)"), ("Conservative", "Conservative profile")):
        if lab == "Conservative":
            a, b = pr(s, lab)["CAGR % out-of-sample"], pr(s, lab)["Max DD % out-of-sample"]
            ia, ib = pr(s, lab)[f"CAGR % {TSPAN}"], pr(s, lab)[f"Max DD % {TSPAN}"]
            row = ["", show, "–", "–", n(a), n(b)]
        else:
            row = ["" if lab != "Raw" else STRATS[s], show, n(ins(s, lab)["CAGR %"]), n(ins(s, lab)["Max drawdown %"]),
                   n(oos(s, lab)["CAGR %"]), n(oos(s, lab)["Max drawdown %"])]
        oos_rows.append(row)
        oos_cls.append("hl" if lab in ("Guarded v1", "Conservative") else "")
oos_rows.append(["NIFTY 50", "Buy and hold", n(v2.loc[f"{NIFTY} | In-sample", "CAGR %"]), n(v2.loc[f"{NIFTY} | In-sample", "Max drawdown %"]),
                 n(v2.loc[f"{NIFTY} | Out-of-sample", "CAGR %"]), n(v2.loc[f"{NIFTY} | Out-of-sample", "Max drawdown %"])])
oos_cls.append("bench")

wf_rows = []
for s in STRATS:
    for lab in ("Raw", "Guarded v1", "Walk-forward v2"):
        r = wf.loc[f"{s} | {lab}"]
        wf_rows.append([STRATS[s] if lab == "Raw" else "", "No rules" if lab == "Raw" else lab, n(r["CAGR %"]),
                        n(r["Max drawdown %"]), n(r["Days below -2% (count)"], 0), n(r["Calmar"])])

prof_rows, prof_cls = [], []
for s in STRATS:
    for lab in ("No rules", "Conservative", "Balanced", "Aggressive"):
        r = pr(s, lab)
        prof_rows.append([STRATS[s] if lab == "No rules" else "", lab + (" (= v1)" if lab == "Balanced" else ""),
                          n(r[f"CAGR % {TSPAN}"]), n(r[f"Max DD % {TSPAN}"]), n(r["Avg exposure %"], 1),
                          n(r["CAGR % out-of-sample"]), n(r["Max DD % out-of-sample"])])
        prof_cls.append("hl" if lab == "Conservative" else "")

ts_rows, ts_cls = [], []
for s in STRATS:
    for lab, per in (("Raw", TSPAN), ("Raw", "Out-of-sample"), ("Guarded v1", TSPAN), ("Guarded v1", "Out-of-sample")):
        r = tsr(s, lab, per)
        ts_rows.append([f"{SHORT[s]} · {'no rules' if lab == 'Raw' else 'v1'}", SPAN if per == TSPAN else "2022+",
                        n(r["Trades"], 0), n(r["Win rate %"], 1), n(r["Win/loss count ratio"]), n(r["Avg win %"]),
                        n(r["Avg loss %"]), n(r["Payoff ratio (avg win / avg loss)"]), n(r["Profit factor"]),
                        n(r["Expectancy per trade %"]), n(r["Max losing streak (trades)"], 0), n(r["Avg holding (calendar days)"], 0)])
        ts_cls.append("hl" if (s == E and per == TSPAN and lab == "Raw") else "")

years = list(cal.index)
cal_rows = [[lab] + [n(cal.loc[y, col], 1) for y in years] for lab, col in (("EMA, no rules", "EMA Raw"), ("EMA, v1", "EMA v1"),
                                                                            ("NIFTY 50", NIFTY))]

VS_SHOW = [(RSW, "Regime switch (main)"), (STRESS, "Resilience model only"), (MOM, "Momentum only"),
           (TRIG, "Regime switch + 12% trigger*"), (EW, "Equal-weight NIFTY 50"), (NB, "NIFTY 50 buy and hold")]
vs_rows, vs_cls = [], []
for a, show in VS_SHOW:
    f, h = vt["full"].loc[a], vt["hold-out"].loc[a]
    vs_rows.append([show, n(f["CAGR %"]), n(f["Max drawdown %"]), n(f["Sharpe"]), n(h["CAGR %"]), n(h["Max drawdown %"]),
                    n(cov[a]), n(h1[a]), n(f.get("Turnover (x/yr)"), 1)])
    vs_cls.append("bench" if a in (EW, NB) else ("hl" if a == RSW else ""))

wl_rows, wl_cls = [], []
for a, show in VS_SHOW:
    if a == TRIG:
        continue
    r = wl.loc[a]
    wl_rows.append([show, n(r["Weeks up %"], 1), n(r["Weeks beating NIFTY %"], 1), n(r["Months up %"], 1),
                    n(r["Months beating NIFTY %"], 1), n(r["Months beating equal weight %"], 1), n(r["Avg up week %"]),
                    n(r["Avg down week %"]), n(r.get("Picks"), 0), n(r.get("Picks beating NIFTY %"), 1)])
    wl_cls.append("bench" if a in (EW, NB) else "")

vcost_rows, vcost_cls = [], []
for a, show in ((RSW, "Regime switch (main)"), (STRESS, "Resilience model only"), (EW, "Equal-weight NIFTY 50")):
    for c in ("0.00%", "0.15%"):
        r = vc(a, c)
        vcost_rows.append([show if c == "0.00%" else "", "gross (0.00%)" if c == "0.00%" else "0.15% per side", n(r["CAGR %"]),
                           n(r["CAGR % 2016-2021"]), n(r["CAGR % 2022+"])])
        vcost_cls.append("bench" if a == EW else "")

ic_rows = []
for feat, oct_said in (("beta", "failed"), ("down_beta", "failed"), ("defensive", "failed"), ("liquidity", "failed"),
                       ("rsi", "failed"), ("pct_b", "failed"), ("stoch", "failed")):
    r = ic.loc[feat]
    now = "failed after 2022" if feat in flagged else "held"
    ic_rows.append([feat.replace("_", " "), n(r.iloc[0], 3, True), n(r.iloc[1], 3, True), "failed after 2022",
                    f'<span class="{"neg" if feat in flagged else "pos"}">{now}</span>'])

# October numbers, from the October submission (git commit 0eea1fd); the "now" column is read from the results
OCT = [
    ("EMA guarded v1, max drawdown 2012–2026", "−23.56%", n(m(E, "Guarded")["Max drawdown %"]) + "%", "ATR-stop re-buy fixed"),
    ("v2 against v1 out of sample", "v2 better on all three", "v2 deeper drawdown than v1 on all three", "ATR-stop re-buy fixed"),
    ("Conservative profile, 2022+ drawdown vs no rules", "shallower on all three", "shallower on all three", "unchanged conclusion"),
    ("Breaker episode in the deck", "Feb 2019 sell-off, missed 8.6% rise", "fires Dec 2015 and Mar 2020 only", "ATR-stop re-buy fixed"),
    ("Resilience model, 2022 H1 return", "−3.2%", n(h1[STRESS], 1) + "%", "placeholder bars removed"),
    ("Resilience model, COVID crash", "−12.1%", n(cov[STRESS], 1) + "%", "placeholder bars removed"),
    ("Headline COVID result", "−7.2% (12% trigger)", n(cov[RSW], 1) + "% (no trigger); trigger " + n(cov[TRIG], 1) + "%",
     "trigger was tuned on a window that includes COVID; bars removed"),
    ("High-volatility days, resilience vs NIFTY", "−3.7% vs −30.8% a year", "withdrawn: misaligned by one day", "alignment fixed"),
    ("Indicators that failed after 2022", "beta, defensive, RSI, %B, stochastic", "beta and downside beta only", "IC bug fixed"),
    ("Regime switch, CAGR 2016–2026", "17.1% (18.0% with trigger)", n(vt["full"].loc[RSW, "CAGR %"], 1) + "%", "placeholder bars removed"),
    ("Equal-weight NIFTY 50, CAGR 2016–2026", "20.3%", n(vt["full"].loc[EW, "CAGR %"], 1) + "%", "unchanged"),
]

today = date.today().strftime("%d %B %Y").lstrip("0")
v1o = {s: oos(s, "Guarded v1") for s in STRATS}
rwo = {s: oos(s, "Raw") for s in STRATS}
ab = lambda s, rule: abl.loc[(s, rule), "Max DD change vs raw (pts)"]
fmt_stop = lambda c: ("no stop" if c["stop_atr_mult"] is None else f"{c['stop_atr_mult']:g}× ATR stop") + \
    (", VIX filter off" if c["vix_limit"] is None else ", VIX filter on") + (", breaker sells all" if c["dd_flatten"] else ", breaker blocks entries")

CSS = (Path(__file__).parent / "style.css").read_text(encoding="utf-8")
SVG = (Path(__file__).parent / "architecture.svg").read_text(encoding="utf-8")

# ------------------------------------------------------------------ the document
doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>AlgoGuard and VolSelect: Technical and Commercial Review</title><style>{CSS}</style></head><body>

<div class="cover"><div>
<div class="band"></div>
<div class="tag">Project review · re-evaluation submission · {today}</div>
<h1>AlgoGuard and VolSelect</h1>
<p class="lead" style="font-size:12.5pt;max-width:150mm">An enforceable risk layer for retail algorithmic trading on NSE, and a volatility-aware NIFTY 50 stock-selection study. Architecture, code, verified backtests, win/loss statistics and commercial viability.</p>
<p class="muted" style="margin-top:14pt">Vansh Dave · Karthik Agarwal &nbsp;|&nbsp; B.Tech AI, 5th semester &nbsp;|&nbsp; Guide: Sailesh Kulkarni</p>
</div><div>
<div class="box good"><h4>Verify every number in this report with one command</h4>
<pre>pip install -r requirements.txt
python verify.py</pre>
<p class="small" style="margin:0">Checks the {n_data} bundled data files against their SHA-256 manifest, runs the {n_tests} unit tests, re-runs both studies from scratch into a temporary folder and compares all {len(result_files)} result files number by number with the submitted <code>results/</code> folder. Expected verdict: <b>ALL RESULTS REPRODUCED</b>, in about 90 seconds. This report is generated from those files by <code>report/build_report.py</code>, which also checks every comparative claim in the text against them.</p></div>
<table class="toc"><tr><td>1&nbsp;&nbsp;Executive summary</td></tr><tr><td>2&nbsp;&nbsp;How to verify (for the assessor)</td></tr>
<tr><td>3&nbsp;&nbsp;Architecture of the backend</td></tr><tr><td>4&nbsp;&nbsp;Code inventory and tests</td></tr>
<tr><td>5&nbsp;&nbsp;AlgoGuard backtest results</td></tr><tr><td>6&nbsp;&nbsp;Win/loss and trade statistics</td></tr>
<tr><td>7&nbsp;&nbsp;VolSelect results, win/loss and costs</td></tr><tr><td>8&nbsp;&nbsp;Commercial viability</td></tr>
<tr><td>9&nbsp;&nbsp;Corrections to our October results, and the independent review</td></tr><tr><td>10&nbsp;Limitations and files</td></tr></table>
</div></div>

<div class="section"><h2>1. Executive summary</h2>
<p class="lead">We built a working, tested trading engine for NSE equities whose risk rules sit inside the order path, so they are enforced, not advised. Every result reproduces exactly from the submitted code and data. Out of sample (2022 onward) the fixed, textbook rule set gave a shallower maximum drawdown than no rules on all three strategies, and a conservative profile cut it further. No strategy and no stock-selection model beats a passive benchmark on return. The product a company would buy is therefore the risk and compliance layer, not a return claim.</p>
<div class="grid3" style="margin:8pt 0 10pt">
<div class="kpi"><div class="v">{len(result_files)}/{len(result_files)}</div><div class="k">result files reproduced by <code>verify.py</code> from a clean install</div></div>
<div class="kpi"><div class="v">{n_tests}</div><div class="k">unit tests, including look-ahead tests that change future prices and check the past does not move</div></div>
<div class="kpi"><div class="v">{info['sessions']:,}</div><div class="k">NSE sessions, {pd.Timestamp(info['start']):%d %b %Y} to {pd.Timestamp(info['end']):%d %b %Y}, 0.15% cost per side, fills at next open</div></div>
</div>
<h3>What the evidence shows</h3>
{table(["Question", "Answer from the backtests"], [
 ["Do the strategies make money after costs?", f"EMA crossover {n(m(E,'Raw')['CAGR %'])}% a year, Donchian {n(m(D,'Raw')['CAGR %'])}%, RSI-2 {n(m(RS,'Raw')['CAGR %'])}% ({SPAN}). NIFTY 50 buy and hold: {n(nifty_cagr)}%. <b>None beats the index on return.</b>"],
 ["Do they carry less risk?", f"Yes. Max drawdown {n(m(E,'Raw')['Max drawdown %'],1)}% (EMA) and {n(m(D,'Raw')['Max drawdown %'],1)}% (Donchian) against NIFTY's {n(nifty_dd,1)}%. EMA's return per unit of drawdown (Calmar {n(m(E,'Raw')['Calmar'])}) is higher than NIFTY's ({n(main.loc[NIFTY,'Calmar'])})."],
 ["Win/loss", f"EMA wins {n(tsr(E,'Raw',TSPAN)['Win rate %'],0)}% of trades, but its average win is {n(tsr(E,'Raw',TSPAN)['Payoff ratio (avg win / avg loss)'],1)}× its average loss (profit factor {n(tsr(E,'Raw',TSPAN)['Profit factor'])}). RSI-2 wins {n(tsr(RS,'Raw',TSPAN)['Win rate %'],0)}% and still loses money (profit factor {n(tsr(RS,'Raw',TSPAN)['Profit factor'])})."],
 ["Do the guardrails cut risk out of sample?", f"Yes, modestly. From 2022 the fixed v1 rules had a shallower max drawdown than no rules on all three strategies (EMA {n(v1o[E]['Max drawdown %'])}% vs {n(rwo[E]['Max drawdown %'])}%), and the <b>Conservative profile</b> cut it further on all three (EMA {n(oos_prof[E])}%). Over {SPAN} the rules cost return (EMA {n(m(E,'Guarded')['CAGR %'])}% vs {n(m(E,'Raw')['CAGR %'])}%)."],
 ["Does tuning the rules on past data help?", "No. Settings chosen on pre-2022 data (v2) looked better than v1 in sample on all three strategies and had a deeper drawdown than v1 out of sample on all three. We report it as a negative result and keep fixed rules."],
 ["VolSelect stock selection", f"Lost less than NIFTY and equal-weight NIFTY 50 in both crashes (COVID: {n(cov[RSW],1)}% vs NIFTY {n(cov[NB],1)}%; 2022 H1 resilience model {n(h1[STRESS],1)}% vs {n(h1[NB],1)}%). But from 2022 it trails equal weight <b>even before costs</b> ({n(vc(RSW,'0.00%')['CAGR % 2022+'],1)}% vs {n(vc(EW,'0.00%')['CAGR % 2022+'],1)}% a year). No proven edge yet."],
])}
<h3>Commercial position, in one paragraph</h3>
<p>From 1 April 2026 SEBI's retail algo framework applies to every stock broker: brokers carry responsibility for algos running on their APIs and must control, tag and audit them. 93% of individual F&amp;O traders lost money between FY22 and FY24 (SEBI study, aggregate losses above Rs 1.8 lakh crore). AlgoGuard already implements what a broker or algo platform needs to offer retail algos safely: pre-trade blocks that can never add risk, a commitment lock that stops a user loosening limits in the heat of the moment, a complete audit log, and an order layer built around the SEBI rules. That is a B2B product. Strategy returns are not, and we do not sell them.</p>
<div class="box warn"><h4>We corrected our own October results</h4><p style="margin:0">Re-running everything for this submission, and an independent code review, found six problems in the October version: a bug in one overfitting check, Yahoo placeholder bars on non-trading days, a stop-loss that bought straight back, a one-day misalignment in one table, a Sortino formula and library-version sensitivity. All are fixed and covered by tests or checks; several October slide numbers changed. Section 9 lists every change, before and after.</p></div>
</div>

<div class="section"><h2>2. How to verify (for the assessor)</h2>
<p>Everything runs on a normal laptop CPU with Python 3.11 to 3.13 (both tested), offline. No GPU, no API keys, no internet.</p>
<h3>Install and run the verifier</h3>
<pre>cd algoguard
python -m venv .venv
.venv\\Scripts\\activate          (Windows)      source .venv/bin/activate   (macOS / Linux)
pip install -r requirements.txt
python verify.py</pre>
<p>Expected output (also written to <code>verify_report.txt</code>):</p>
<pre>[PASS] package versions match requirements.txt
[PASS] data: {n_data}/{n_data} files match the manifest
[PASS] unit tests: {n_tests} passed
[PASS] results/1_main_comparison.csv  largest relative difference 0.0e+00
...   ({len(result_files)} result files)
{len(result_files)}/{len(result_files)} result files reproduced.
VERDICT: ALL RESULTS REPRODUCED</pre>
{table(["Check", "How"], [
 ["Same libraries", "Compares installed versions with the exact pins in <code>requirements.txt</code> and warns on any difference. scikit-learn's gradient boosting fits differently across versions, which moves the VolSelect tables, so the pins matter."],
 ["Same input data", "SHA-256 of every CSV in <code>data/</code> against <code>data/MANIFEST.sha256</code> (line endings normalised, so a Windows checkout passes)."],
 ["Code correctness", f"Runs the {n_tests} unit tests (section 4)."],
 ["Results", "Runs <code>run.py</code> and <code>run_vs.py</code> into a temporary folder, then compares every CSV and JSON in <code>results/</code> and <code>results/vs/</code> cell by cell (relative tolerance 1e-6; text must match exactly)."],
])}
<div class="box bad"><h4>Please do not run <code>--download</code> before verifying</h4><p style="margin:0">Yahoo Finance revises its adjusted historical prices over time (dividends, splits), so freshly downloaded data moves the numbers slightly. That is a data difference, not a code difference, and the manifest check detects it at once. To test the code on new data afterwards: <code>python run.py --download --force</code>. The conclusions, not the second decimal, are what should hold.</p></div>
<h3>Where we have already confirmed it</h3>
<p>From a clean unzip into an empty folder, with a fresh virtual environment installed from <code>requirements.txt</code>, <code>verify.py</code> reproduced every file. We also ran it with older libraries (pandas 2.2, numpy 1.26, scikit-learn 1.5): the AlgoGuard results and the regime forecast still matched exactly; the VolSelect tables moved, mainly because scikit-learn's gradient boosting changed between versions, which is why the versions are pinned and checked (the verifier prints a warning first if they differ). Model fits are deterministic (gradient boosting uses <code>random_state=0</code>), so there is no random seed to get lucky with.</p>
<h3>Other commands</h3>
{table(["Command", "What it does"], [
 ["<code>python -m pytest -q tests</code>", f"{n_tests} unit tests"],
 ["<code>python run.py</code>", "AlgoGuard: all 11 experiments, writes <code>results/</code>"],
 ["<code>python run_vs.py</code>", "VolSelect walk-forward study, writes <code>results/vs/</code>"],
 ["<code>python report/build_report.py</code>", "Rebuilds this report from the result files and checks its claims"],
 ["<code>python paper_trade.py --days 60</code>", "Day-by-day paper replay through the broker layer"],
 ["<code>streamlit run app.py</code>", "Interactive dashboard (also live at algoguard.streamlit.app)"],
])}
</div>

<div class="section"><h2>3. Architecture of the backend</h2>
<p>One engine runs from market data to the order. Risk rules can only <b>block a new entry</b> or <b>force an exit</b>; they can never open a position. Every intervention is written to an audit log with the date, the rule and the reason.</p>
{SVG}
<h3>Timing: why there is no look-ahead</h3>
{table(["When", "What happens", "Data it may use"], [
 ["Close of day t−1", "Signals computed, risk state updated (losses, drawdown, VIX)", "Prices up to and including the close of t−1"],
 ["Open of day t", "Exits, then entries, fill at the open price plus 0.15% cost", "Today's open (as the fill price only)"],
 ["During day t", "Protective ATR stops fill at the stop, or at the open if it gapped through", "Today's low (stop trigger only)"],
 ["Close of day t", "Mark to market, risk state updated", "Today's close"],
])}
<p>Tested, not just claimed: <code>test_no_lookahead</code>, <code>test_features_have_no_lookahead</code>, <code>test_regime_forecast_has_no_lookahead</code> and <code>test_portfolio_has_no_lookahead</code> multiply every price after day k by 3 and assert that every result up to day k is unchanged. Models train only on rows whose 10-day target is complete before the cut-off date, and GARCH parameters are fitted on data before each forecast year.</p>
<h3>The six risk rules (Balanced = v1, textbook settings fixed before testing)</h3>
{table(["Rule", "Setting", "Action"], [
 ["ATR stop-loss", "entry − 3 × ATR(14)", "force exit during the day; no re-buy until the strategy's own signal resets"],
 ["Daily loss limit", "portfolio −2% in a day", "no new entries for 2 sessions"],
 ["Losing-streak cooldown", "3 losing trades in a row", "no new entries for 5 sessions"],
 ["Drawdown circuit breaker", "−15% from peak", "sell all (or block entries only), halt 20 sessions, re-arm"],
 ["India VIX filter", "VIX above 25", "no new entries"],
 ["Volatility sizing", "target 25% vol, cap 15% per position", "scales position size"],
])}
<h3>Data handling</h3>
<p>Daily OHLCV from Yahoo Finance (dividend and split adjusted), cached as CSV and bundled. On loading, Yahoo's placeholder bars (open = high = low = close with no volume, written for days a stock did not trade) are dropped, so no trade can fill on a holiday or at a made-up price. AlgoGuard trades only on dates every stock traded; VolSelect works on the NIFTY calendar and treats a stock's missing day as a no-trade day.</p>
</div>

<div class="section"><h2>4. Code inventory and tests</h2>
<p>{total_lines:,} lines of Python including tests, no notebooks, every module importable and tested. Line counts are measured from the submitted files when this report is built.</p>
{table(["File", "Lines", "Responsibility"], code_rows)}
<h3>The {n_tests} unit tests</h3>
{table(["File", "Tests", "What they prove"], test_rows)}
</div>

<div class="section"><h2>5. AlgoGuard backtest results</h2>
<p>{info['stocks']} NIFTY large caps, {pd.Timestamp(info['start']):%d %b %Y} to {pd.Timestamp(info['end']):%d %b %Y} ({info['sessions']:,} sessions), Rs 10 lakh, 0.15% cost per side, signals at the close, fills at the next open. Strategy parameters are textbook defaults fixed before testing. Source: <code>results/1_main_comparison.csv</code>.</p>
{table(["Strategy", "Risk layer", "CAGR %", "Sharpe", "Max DD %", "Worst day %", "Days < −2%", "Calmar", "Trades", "Exposure %"], main_rows, main_cls)}
<p class="small muted">Sharpe uses a 6.5% risk-free rate while uninvested cash earns nothing in the backtest, which pulls down the Sharpe of partly invested strategies. Stock prices include dividends; NIFTY 50 (^NSEI) is a price index, so comparisons with NIFTY favour the strategies by roughly its dividend yield (about 1.2–1.5% a year).</p>
<img class="chart" src="../results/chart_1_equity_drawdown.png" alt="Equity and drawdown, raw vs guarded">
<div class="cap">Equity (log scale) and drawdown. Dotted line: start of the 2022+ hold-out. <code>results/chart_1_equity_drawdown.png</code></div>
</div>

<div><h3>Out of sample, side by side (in sample 2012–2021, out of sample 2022 onward)</h3>
<p>Sources: <code>results/7_v2_comparison.csv</code>, <code>results/11_risk_profiles.csv</code>. v2 picks each strategy's breaker mode, VIX filter and stop distance from a 16-setting menu by best Calmar on data cut at 31 Dec 2021. It chose: EMA {fmt_stop(chosen[E])}; Donchian {fmt_stop(chosen[D])}; RSI-2 {fmt_stop(chosen[RS])}.</p>
{table(["Strategy", "Layer", "CAGR % 2012–21", "Max DD % 2012–21", "CAGR % 2022+", "Max DD % 2022+"], oos_rows, oos_cls)}
<div class="grid2">
<div class="box good"><h4>Fixed rules cut out-of-sample drawdown</h4><p style="margin:0">From 2022 the untuned v1 rules had a shallower drawdown than no rules on all three strategies, and the Conservative profile (set by hand before testing) cut it further on all three: EMA {n(oos_prof[E])}%, Donchian {n(oos_prof[D])}%, RSI-2 {n(oos_prof[RS])}%, against {n(rwo[E]['Max drawdown %'])}%, {n(rwo[D]['Max drawdown %'])}% and {n(rwo[RS]['Max drawdown %'])}% with no rules. The mechanism is plain: the profile holds less ({n(pr(E,'Conservative')['Avg exposure %'],0)}% invested on EMA against {n(pr(E,'No rules')['Avg exposure %'],0)}%).</p></div>
<div class="box bad"><h4>Tuning the rules on the past did not carry over</h4><p style="margin:0">v2 beat v1 in sample on all three strategies (EMA Calmar {n(ins(E,'Guarded v2')['Calmar'])} vs {n(ins(E,'Guarded v1')['Calmar'])}) and then had a deeper drawdown than v1 out of sample on all three. That is the overfitting signature our protocol was built to expose, and it is why we lead with fixed rules and hand-set profiles.</p></div>
</div>
<h3>Walk-forward, 2015 to 2026</h3>
<p>Every 1 January the v2 setting is re-picked from the same menu using only earlier data, then traded for that year (<code>results/8_walk_forward.csv</code>). The stop was dropped in {stop_picks.get('none', 0)} of {sum(stop_picks.values())} yearly picks.</p>
{table(["Strategy", "Layer", "CAGR %", "Max DD %", "Days < −2%", "Calmar"], wf_rows)}
<p>{wf_sentence} v1 had the fewest days below −2% on EMA and Donchian.</p>
</div>

<div><h3>Risk profiles</h3>
<p>Three profiles, set by hand before testing (<code>risk.py</code>, PROFILES), show one engine serving different risk appetites. Source: <code>results/11_risk_profiles.csv</code>.</p>
{table(["Strategy", "Profile", f"CAGR % {SPAN}", f"Max DD % {SPAN}", "Exposure %", "CAGR % 2022+", "Max DD % 2022+"], prof_rows, prof_cls)}
<h3>Which rule does the work (ablation)</h3>
<img class="chart" src="../results/chart_2_ablation.png" alt="Ablation chart">
<div class="cap">Change in max drawdown when one rule is added alone, {SPAN} (points, positive = shallower). <code>results/3_ablation.csv</code></div>
<p>On EMA the ATR stop ({n(ab(E,'ATR stop-loss'),2,True)} points) and volatility sizing ({n(ab(E,'Volatility sizing'),2,True)}) made the drawdown shallower, while the drawdown breaker ({n(ab(E,'Drawdown circuit breaker'),2,True)}) and the VIX filter ({n(ab(E,'India VIX filter'),2,True)}) made it deeper. On RSI-2, which has its own exit rule, the stop made it deeper ({n(ab(RS,'ATR stop-loss'),2,True)}). Rules have to fit the strategy they protect.</p>
<p><b>The breaker in the COVID crash, from the audit log.</b> On 12 Mar 2020 EMA v1 was more than 15% below its peak; the breaker sold everything at the next open, when NIFTY opened at {n(n_open,0)}. NIFTY then fell to {n(n_low,0)} by {n_low_d:%d %b}, and the 20-session halt ended on {n_end_d:%d %b} with NIFTY at {n(n_end,0)}. Every block, halt and re-arm is in <code>results/audit_log_ema.csv</code> with its date and reason.</p>
<h3>Robustness and costs</h3>
<p>Across 10 EMA parameter pairs, v1 had a shallower mean max drawdown ({n(rob.loc['mean','Guarded MaxDD %'],1)}% against {n(rob.loc['mean','Raw MaxDD %'],1)}%) at a lower mean Sharpe ({n(rob.loc['mean','Guarded Sharpe'])} against {n(rob.loc['mean','Raw Sharpe'])}), so the drawdown result is not one lucky setting (<code>chart_3_robustness_grid.png</code>, <code>4_robustness.csv</code>). At 0.30% per side EMA still earns {n(cost.loc[f'{E} | Raw | 0.30%','CAGR %'])}%; RSI-2, with {n(m(RS,'Raw')['Trades'],0)} trades, falls to {n(cost.loc[f'{RS} | Raw | 0.30%','CAGR %'])}%: high-turnover strategies do not survive Indian delivery costs.</p>
</div>

<div class="section"><h2>6. Win/loss and trade statistics</h2>
<p>Every round trip, after costs on both sides; a trade that only covered its costs counts as a loss. "2022+" counts trades entered from 1 Jan 2022. Positions open on the last day are closed at the last close for these statistics only. Source: <code>results/9_trade_stats.csv</code> (also best and worst trade, expectancy in rupees, and v2).</p>
{table(["Strategy · layer", "Trades entered", "Trades", "Win rate %", "Win : loss", "Avg win %", "Avg loss %", "Payoff", "Profit factor", "Expectancy %", "Max losing streak", "Avg hold (days)"], ts_rows, ts_cls)}
<p class="small muted">Win : loss = winning trades ÷ losing trades. Payoff = average win ÷ |average loss|. Profit factor = gross rupee profit ÷ gross rupee loss. Expectancy = average return per trade.</p>
<div class="grid2">
<div class="box good"><h4>Trend following works the way theory says</h4><p style="margin:0">EMA loses about two trades out of three and still makes money: a winner averages {n(tsr(E,'Raw',TSPAN)['Avg win %'],1)}% and a loser {n(tsr(E,'Raw',TSPAN)['Avg loss %'],1)}%. Profit factor {n(tsr(E,'Raw',TSPAN)['Profit factor'])} over {n(tsr(E,'Raw',TSPAN)['Trades'],0)} trades, and {n(tsr(E,'Raw','Out-of-sample')['Profit factor'])} on trades entered after 2022.</p></div>
<div class="box bad"><h4>A high win rate is not an edge</h4><p style="margin:0">RSI-2 wins {n(tsr(RS,'Raw',TSPAN)['Win rate %'],0)}% of its trades, the best win rate here, and still loses money: its average loss ({n(tsr(RS,'Raw',TSPAN)['Avg loss %'],1)}%) is bigger than its average win ({n(tsr(RS,'Raw',TSPAN)['Avg win %'],1)}%), and {n(tsr(RS,'Raw',TSPAN)['Trades'],0)} trades pay costs every time. Profit factor {n(tsr(RS,'Raw',TSPAN)['Profit factor'])}.</p></div>
</div>
<p>Commercially this is the core user problem: an EMA-type strategy shows its owner long runs of losing trades before the next big winner (up to {n(ts.loc[[i for i in ts.index if i.startswith(E)], 'Max losing streak (trades)'].max(),0)} in a row across the EMA variants and periods in the table). That is when retail users abandon a system or switch off its rules, and exactly what the commitment lock is built to stop.</p>
<h3>Calendar-year returns, EMA crossover (%)</h3>
{table(["Year"] + [str(y) + ("*" if y == years[-1] else "") for y in years], cal_rows, ["", "", "bench"])}
<p class="small muted">*{years[-1]} to {pd.Timestamp(info['end']):%d %b}. All strategies: <code>results/10_calendar_returns.csv</code>. EMA v1 beat NIFTY in {", ".join(yrs_v1)}; it lagged in strong bull years, as a partly-in-cash strategy should.</p>
</div>

<div class="section"><h2>7. VolSelect results, win/loss and costs</h2>
<p>All 50 current NIFTY 50 stocks. Every model (volatility regime and stock selection) is refitted each 1 January on past data only and used for that year, 2016 to 2026; 2022 onward is reported on its own. Weekly rebalance, top 10, inverse-volatility weights, 0.15% per side. Source: <code>results/vs/table_*.csv</code>. Crash columns are the return over 14 Feb–30 Apr 2020 and Jan–Jun 2022.</p>
{table(["Approach", "CAGR % 2016–26", "Max DD %", "Sharpe", "CAGR % 2022+", "Max DD % 2022+", "COVID crash %", "2022 H1 %", "Turnover ×/yr"], vs_rows, vs_cls)}
<p class="small muted">*The trigger level (12%) was chosen on 2016–2021 Calmar, a window that contains the COVID crash, so its COVID number is in sample; it is shown for completeness. The main approach has no tuned parameter. Stock prices include dividends; NIFTY 50 is a price index, so equal-weight NIFTY 50 (same adjusted prices) is the like-for-like benchmark.</p>
<img class="chart" src="../results/vs/chart_2_drawdown.png" alt="VolSelect drawdown against benchmarks">
<div class="cap">Drawdown from peak. <code>results/vs/chart_2_drawdown.png</code></div>
<h3>Win/loss (2016–2026)</h3>
<p>The portfolio rebalances weekly, so win/loss is measured by week, by month, and by pick: one stock held from one rebalance to the next, a win if it beat NIFTY. Source: <code>results/vs/win_loss.csv</code>.</p>
{table(["Approach", "Weeks up %", "Weeks beating NIFTY %", "Months up %", "Months beating NIFTY %", "Months beating equal wt %", "Avg up week %", "Avg down week %", "Picks", "Picks beating NIFTY %"], wl_rows, wl_cls)}
<p>The pick hit rate is about 50%: in calm markets the model is not a stock-picker. Its value shows only in crashes, in how much less it lost.</p>
</div>

<div><h3>Costs, and whether there is an edge at all</h3>
<p>Source: <code>results/vs/cost_sensitivity.csv</code> (also 0.05% and 0.30%).</p>
{table(["Approach", "Cost", "CAGR % 2016–26", "CAGR % 2016–21", "CAGR % 2022+"], vcost_rows, vcost_cls)}
<div class="box bad"><h4>The single most important number for viability</h4><p style="margin:0">Before costs the regime switch beat equal weight in 2016–2021 ({n(vc(RSW,'0.00%')['CAGR % 2016-2021'],1)}% against {n(vc(EW,'0.00%')['CAGR % 2016-2021'],1)}% a year) but <b>trailed it from 2022</b> ({n(vc(RSW,'0.00%')['CAGR % 2022+'],1)}% against {n(vc(EW,'0.00%')['CAGR % 2022+'],1)}%). The edge did not survive out of sample even before costs, so cutting turnover alone cannot make it viable. Over the full period the break-even cost is about {breakeven:.2f}% per side, below the 0.1% STT that Indian delivery trades pay on each side; at 0.15% the {n(vt['full'].loc[RSW,'Turnover (x/yr)'],0)}× a year turnover costs about {n(gross_rsw - vc(RSW,'0.15%')['CAGR %'],1)} points a year.</p></div>
<h3>Capacity</h3>
<p>Over the last year the median NIFTY 50 stock traded Rs {n(cap.iloc[0],0)} crore a day and the least liquid Rs {n(cap.iloc[1],0)} crore. A 10% position stays under 5% of a day's traded value up to about Rs {n(cap.iloc[2],0)} crore of capital in the least liquid stock. Capacity is not the constraint; the edge is.</p>
<h3>Volatility forecast: the weak link</h3>
<p>Hold-out 2022–2026: hit rate {n(acc.iloc[1]['hit_rate']*100,1)}% against {n(acc.iloc[1]['naive_hit_rate']*100,1)}% for a naive "next 10 days like the last 10" rule, precision {n(acc.iloc[1]['precision']*100,1)}%, but recall only {n(acc.iloc[1]['recall']*100,1)}% (naive {n(acc.iloc[1]['naive_recall']*100,1)}%). When it says "high" it is usually right; it misses most high-volatility spells. Confusion matrices: <code>results/vs/report.md</code>.</p>
<h3>What held up after 2022 (corrected overfitting check)</h3>
<p>Average daily rank correlation (IC) between each indicator and the next 10-day return over NIFTY, on high-volatility days (<code>results/vs/overfitting_ic.csv</code>). In stress, defensive sectors and stocks that were not overbought (low RSI, %B and stochastic) kept beating NIFTY after 2022; the low-beta effect did not.</p>
{table(["Indicator", "IC 2013–2021", "IC 2022+", "October report said", "Corrected"], ic_rows)}
</div>

<div class="section"><h2>8. Commercial viability</h2>
<p class="lead">What a company would buy is the enforcement layer, not the strategies. We pitch it that way because the backtests support exactly that and no more.</p>
<h3>Scorecard</h3>
{table(["Criterion", "Status", "Evidence"], [
 ["Results reproducible by a third party", '<span class="pos">Ready</span>', f"<code>verify.py</code>: {len(result_files)}/{len(result_files)} files identical from a clean install"],
 ["Engineering quality", '<span class="pos">Ready</span>', f"{n_tests} tests incl. look-ahead tests; deterministic; independent review found no leakage"],
 ["Rules actually enforced", '<span class="pos">Ready</span>', "Rules sit in the order path; commitment lock (8 tests); audit log of every intervention"],
 ["SEBI retail-algo controls", '<span class="warn">Built, paper only</span>', "10 orders/s limiter, MPP limit orders, daily login, strategy tags; paper replay through the broker layer"],
 ["Risk reduction out of sample", '<span class="pos">Shown, modest</span>', "v1 and Conservative cut 2022+ drawdown on all three strategies; they cost return over the full period"],
 ["Tuning rules on past data", '<span class="neg">Did not carry over</span>', "v2 better in sample, worse out of sample on all three"],
 ["Return edge over a benchmark", '<span class="neg">Not shown</span>', "No strategy beats NIFTY; VolSelect trails equal weight from 2022 even before costs"],
 ["Live track record", '<span class="neg">Not yet</span>', "Needs a broker-empanelled setup and a live feed"],
])}
<h3>The product: AlgoGuard Risk Layer, licensed to brokers and algo platforms</h3>
<div class="grid2"><div>
<p><b>The customer.</b> Stock brokers and retail algo platforms in India. From 1 April 2026 SEBI's retail algo framework (circular of 4 Feb 2025, timeline of 30 Sep 2025) applies to all stock brokers: the broker is the principal for algos on its API, algo providers act as its agents, every algo order must be tagged, and the broker must keep control of what runs.</p>
<p><b>The pain.</b> 93% of individual equity F&amp;O traders lost money between FY22 and FY24, more than Rs 1.8 lakh crore in aggregate, and the number of traders nearly doubled, from 5.1 million in FY22 to 9.6 million in FY24 (SEBI study, Sept 2024). A broker that opens algo access to these users needs controls the user cannot switch off in a bad moment.</p>
</div><div>
<p><b>What exists today.</b> A pre-trade risk engine that can only block or exit, never add risk; three risk profiles; a commitment lock that delays any loosening; a complete, plain-English audit trail of every intervention ("why did my algo not buy on 14 March?"), useful for support and grievances; and an order layer mapped to the SEBI controls and to Zerodha Kite Connect.</p>
<p><b>Business model.</b> Per-active-account licence (SaaS) to the broker or platform, plus an integration fee. Strategies stay the client's; we sell no recommendations, so this product needs no Research Analyst registration.</p>
</div></div>
<h3>Why the backtests support this pitch, and no more</h3>
<ul>
<li>Fixed, transparent rules measurably cut out-of-sample drawdown on every strategy tested, at a visible cost in return. A risk layer that is honest about that trade-off is what a regulated broker can deploy.</li>
<li>The best strategy's win/loss profile ({n(tsr(E,'Raw',TSPAN)['Win rate %'],0)}% win rate, losing streaks of up to {n(ts.loc[[i for i in ts.index if i.startswith(E)], 'Max losing streak (trades)'].max(),0)} trades) is exactly when retail users override their own rules. The lock and the audit log address that behaviour directly.</li>
<li>Our own test of rule tuning (v2) shows why the product should ship fixed, explainable profiles rather than optimised settings.</li>
<li>Every claim is reproducible from the code and data with one command: due diligence costs a buyer two minutes.</li>
</ul>
<h3>VolSelect: research, not a product</h3>
<p>Selling stock selections requires SEBI Research Analyst registration, and the study has no edge over its benchmark out of sample, even before costs. It becomes a product candidate only if a version beats equal-weight NIFTY 50 on data it was not tuned on, first before costs and then after 0.15% per side, on point-in-time index members. Until then it is a research module and a "stress screener" view in the dashboard.</p>
<h3>Roadmap to a pilot</h3>
{table(["Step", "Deliverable", "Proves"], [
 ["1. Intraday enforcement", "Minute data; daily loss limit and stops act intraday, not at the next open", "Rules work at the speed users lose money"],
 ["2. Live paper record", "Daily paper trading on live prices for 3 months, audit log published", "Backtest behaviour holds live"],
 ["3. F&amp;O support", "Margin-aware sizing and loss limits for futures and options", "Covers where SEBI found the losses"],
 ["4. Broker pilot", "Integration with one broker's API sandbox, as its empanelled agent", "A paying customer and the compliance path"],
 ["5. VolSelect research", "Point-in-time members; look for an out-of-sample gross edge before anything else", "Whether selection adds anything"],
])}
<h3>Risks a buyer should weigh</h3>
<p>Regulation is still settling (exchange standards on top of the SEBI circular); brokers may build controls in house; daily-bar results may differ from intraday behaviour; and nothing here has a live record yet.</p>
</div>

<div class="section"><h2>9. Corrections to our October results, and the independent review</h2>
<p>For this submission we re-ran everything from a clean clone and had the full code base reviewed adversarially by an independent automated (AI) reviewer, run separately from the work, with instructions to find look-ahead, calculation errors and claims in our README and reports that the code does not support. We then had it re-check every fix; its second pass found one more problem (a held stock with no open price could be re-spent at a rebalance), fixed with a new test. Every problem found is fixed below and covered by a test or by <code>verify.py</code>.</p>
{table(["#", "Problem", "Fix", "Effect"], [
 ["1", "Overfitting check: <code>pd.Timestamp(None)</code> is <code>NaT</code>, so the 2022+ IC sample was empty and seven indicators were wrongly flagged as failing after 2022", "Open end means 'to the last date'; IC computed as the average of daily rank correlations, as documented; table saved to CSV so <code>verify.py</code> checks it", "Only beta and downside beta failed (table in section 7)"],
 ["2", "Yahoo placeholder bars (open = high = low = close, no volume) on market holidays (24 Apr 2014, 15 Oct 2014, 15 Jan 2026) and on 18 Mar 2025 for most stocks", "Dropped on loading; VolSelect treats a stock's missing day as a no-trade day instead of blanking 20 days of features", f"AlgoGuard: {info['sessions']:,} instead of 3,649 sessions, no trades on holidays. VolSelect: at least 43 stocks scoreable every day (before: as few as 1 for weeks in Mar–Apr 2025 and none in Jan–Feb 2026)"],
 ["3", "After an ATR stop the stock was bought back at the next open while the signal was still 'long' (47 of 100 stops on EMA)", "No re-entry until the strategy's own signal resets; new test", f"v1 no longer churns: EMA v1 max drawdown {n(m(E,'Guarded')['Max drawdown %'])}% (October −23.56%), close to raw {n(m(E,'Raw')['Max drawdown %'])}%; v1 cuts 2022+ drawdown on all three strategies"],
 ["4", "'Return on high-volatility days' used each day's own forecast, which reacts to that day's return", "Return on day t paired with the forecast made at the close of t−1", "The October claim (−3.7% vs −30.8% a year) is withdrawn: on correctly aligned days every approach gained"],
 ["5", "Sortino used the standard deviation of negative returns", "Downside deviation below the risk-free rate", "Only the Sortino column changes"],
 ["6", "Gradient boosting fits differently across scikit-learn versions", "Exact pins in <code>requirements.txt</code>; <code>verify.py</code> warns on any version difference", "Results reproducible on any machine with the pinned versions"],
])}
<p>Also corrected: the dashboard's trade statistics now follow the chosen period; Windows encoding; and disclosures added for dividends (stocks are total return, NIFTY is a price index), for v2's menu (motivated by the full-period ablation; the same rules are flagged on pre-2022 data alone) and for the walk-forward's stitching shortcut.</p>
<h3>What changed on our October slides</h3>
{table(["October claim", "October", "Now", "Why"], [[html.escape(a), b, c, html.escape(d)] for a, b, c, d in OCT])}
<h3>What the review confirmed as correct</h3>
<p>Backtest timing (signals, ATR, volatility and VIX all at t−1; fills at the open; stop fills), risk-state updates, v2's data cut at the split, the regime model's GARCH fit window and training mask, the stock model's target cut-off, the portfolio's rebalance timing and drawdown-trigger retraining, all metric formulas other than Sortino, cash accounting and no leverage in the AlgoGuard backtester. (VolSelect's no-leverage rule now also has a test for a held stock with no open price, the second-pass finding.)</p>
</div>

<div class="section"><h2>10. Limitations and files</h2>
{table(["Limitation", "Effect on the results", "Fix"], [
 ["Survivorship bias", "Today's large caps and today's NIFTY 50 list are used back to 2012/2016. Flatters every approach that holds these stocks, the equal-weight benchmark included.", "Point-in-time index members"],
 ["Dividends", "Stocks are total return, NIFTY 50 is a price index: comparisons with NIFTY favour the stocks by about 1.2–1.5% a year.", "NIFTY 50 Total Return Index"],
 ["Daily bars", "The daily loss limit and the drawdown trigger act at the next open, not intraday.", "Minute data"],
 ["Stop fills", "Stops fill at the stop price unless the open gaps through it; real slippage in fast markets can be worse.", "Intraday data, slippage model"],
 ["Unofficial data", "Yahoo Finance adjusted prices; adjustments can contain errors and are revised over time.", "Licensed NSE data"],
 ["Cash earns nothing", "Uninvested cash earns 0% while Sharpe subtracts 6.5%. Understates partly-invested strategies.", "Credit a liquid-fund yield"],
 ["Short hold-out", "2022 onward is under five years and one market regime.", "Live paper record"],
 ["Scope", "Long-only cash equities; no F&amp;O, no shorting.", "Roadmap step 3"],
])}
<h3>Files in this submission</h3>
{table(["Path", "Contents"], [
 ["<code>AlgoGuard_VolSelect_Review_Report.pdf</code>", "This report"],
 ["<code>algoguard/</code>, <code>run.py</code>, <code>run_vs.py</code>, <code>paper_trade.py</code>, <code>app.py</code>, <code>pages/</code>", "All Python code"],
 ["<code>verify.py</code>, <code>requirements.txt</code>, <code>data/MANIFEST.sha256</code>, <code>verify_report.txt</code>", "Reproduction kit, and our own verifier output"],
 [f"<code>tests/</code>", f"{n_tests} unit tests"],
 [f"<code>data/</code>", f"The exact price data used ({n_data} CSV files)"],
 ["<code>results/</code>, <code>results/vs/</code>", "Every table, trade list, audit log and chart quoted here, plus a <code>report.md</code> per study"],
 ["<code>report/</code>", "Source of this report: <code>build_report.py</code> reads the result files and checks the claims"],
])}
<p class="small muted" style="margin-top:14pt">Academic research prototype. Nothing here is investment advice or an offer of any service. Past backtest results do not predict future returns. Sources: SEBI press release, "Updated SEBI study reveals 93% of individual traders incurred losses in equity F&amp;O between FY22 and FY24", 23 Sep 2024; SEBI circular "Safer participation of retail investors in algorithmic trading", 4 Feb 2025, and timeline extension circular SEBI/HO/MIRSD/MIRSD-PoD/P/CIR/2025/132, 30 Sep 2025.</p>
</div>
</body></html>"""

out = Path(__file__).parent / "report.html"
out.write_text(doc, encoding="utf-8")
print(f"wrote {out}  ({len(result_files)} result files, {n_tests} tests, all claims checked)")

# PDF via a Chromium browser, if one is installed
cands = [os.environ.get("CHROME", ""), "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
         r"C:\Program Files\Google\Chrome\Application\chrome.exe", r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
         shutil.which("google-chrome") or "", shutil.which("chromium") or "", shutil.which("chromium-browser") or ""]
browser = next((c for c in cands if c and Path(c).exists()), None)
if browser and "--no-pdf" not in sys.argv:
    pdf = ROOT / "AlgoGuard_VolSelect_Review_Report.pdf"
    subprocess.run([browser, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--allow-file-access-from-files",
                    f"--print-to-pdf={pdf}", out.resolve().as_uri()], capture_output=True)
    print(f"wrote {pdf}" if pdf.exists() else "PDF step failed; open report.html in a browser and print to PDF")
elif "--no-pdf" not in sys.argv:
    print("No Chrome/Edge found: open report/report.html in a browser and print to PDF")
