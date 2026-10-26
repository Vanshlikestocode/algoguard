"""Volatility-aware NIFTY 50 stock selection: walk-forward study. ACADEMIC RESEARCH PROTOTYPE,
NOT INVESTMENT ADVICE.

    python run_vs.py --download    # first time: NIFTY 50 data into data/nifty50/
    python run_vs.py               # writes results/vs/ (tables, 5 charts, audit log, report.md)

Every model (volatility regime, stock selection) is refitted each 1 January on past data only and
used for that year. 2016-2021 is the development period; 2022 onward is the hold-out. All design
settings (K=10, weekly rebalance, regime cut-offs 0.3/0.5, horizons) were fixed before running.
"""
from __future__ import annotations

import argparse
import copy
import json
import warnings
from pathlib import Path

import matplotlib
import matplotlib.ticker

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from algoguard import features, portfolio, regime, selection, universe
from algoguard.metrics import drawdown, summarize

warnings.filterwarnings("ignore")
OUT = Path(__file__).resolve().parent / "results" / "vs"
FIRST, SPLIT = 2016, pd.Timestamp("2022-01-01")
PERIODS = {"Full walk-forward 2016–2026": ("2016-01-01", None), "Development 2016–2021": ("2016-01-01", "2021-12-31"),
           "Hold-out 2022–2026": ("2022-01-01", None), "COVID crash (14 Feb–30 Apr 2020)": ("2020-02-14", "2020-04-30"),
           "2022 sell-off (Jan–Jun 2022)": ("2022-01-01", "2022-06-30")}
C_BLUE, C_RED, C_GREY, C_GOLD = "#1F6F8B", "#B4483C", "#8A8A8A", "#C9A227"


def md(df, fmt="{:.2f}"):
    head = "| " + " | ".join([df.index.name or ""] + list(map(str, df.columns))) + " |"
    rows = [head, "|" + "---|" * (len(df.columns) + 1)]
    for i, r in df.iterrows():
        rows.append("| " + " | ".join([str(i)] + [fmt.format(v) if isinstance(v, (float, np.floating)) else str(v) for v in r]) + " |")
    return "\n".join(rows)


def stats(eq: pd.Series, start, end, turnover: pd.Series | None = None) -> dict:
    e = eq.loc[start:end]
    if len(e) < 3:
        return {}
    m = summarize(e / e.iloc[0])
    out = {k: m[k] for k in ["CAGR %", "Sharpe", "Max drawdown %", "Worst day %", "Days below -2% (count)", "Calmar"]}
    if turnover is not None and len(turnover):
        t = turnover.loc[start:end]
        yrs = max((e.index[-1] - e.index[0]).days / 365.25, 0.1)
        out["Turnover (x/yr)"] = t.sum() / yrs
    if end is not None and start is not None and (pd.Timestamp(end) - pd.Timestamp(start)).days < 200:
        out["Period return %"] = (e.iloc[-1] / e.iloc[0] - 1) * 100
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--download", action="store_true")
    ap.add_argument("--k", type=int, default=10)
    a = ap.parse_args()
    if a.download:
        universe.download()
    OUT.mkdir(parents=True, exist_ok=True)
    prices, nifty, vix = universe.load()
    nc = nifty["close"]
    print(f"{len(prices)} NIFTY 50 stocks, {nc.index[0].date()} to {nc.index[-1].date()}")

    # 1. volatility regime (walk-forward)
    f = regime.walk_forward(nc, vix, FIRST)
    acc = {lab: regime.accuracy(f, *span) for lab, span in
           {"Development 2016–2021": ("2016", "2021"), "Hold-out 2022–2026": ("2022", None)}.items()}

    # 2. features
    P = features.panel(prices, nc, f["rv10"] > f["thr"], universe.constituents())
    wide = lambda col: P[col].unstack("ticker")

    # 3. yearly models and score frames
    idx = nc.index[nc.index >= f"{FIRST}-01-01"]
    tick = sorted(prices)
    O = pd.DataFrame({t: prices[t]["open"].reindex(idx) for t in tick})
    C = pd.DataFrame({t: prices[t]["close"].reindex(idx) for t in tick})
    vol = wide("vol_20").reindex(index=idx, columns=tick)
    scores = {"momentum": wide("mom_120").reindex(index=idx, columns=tick),
              "low_vol": -vol,
              "equal_weight": vol.notna().astype(float).where(vol.notna())}
    stress, stress_gb, imps, log, gb_auc = [], [], {}, [], []
    from sklearn.metrics import roc_auc_score
    for year in range(FIRST, idx[-1].year + 1):
        end = pd.Timestamp(f"{year - 1}-12-31")
        lr, gb = selection.fit(P, f["y"], end), selection.fit(P, f["y"], end, kind="gb")
        stress.append(selection.score(lr, P, "high", f"{year}-01-01", f"{year}-12-31"))
        stress_gb.append(selection.score(gb, P, "high", f"{year}-01-01", f"{year}-12-31"))
        imps[year] = selection.importance(lr)
        log.append({"date": pd.Timestamp(f"{year}-01-01"), "rule": "walk_forward", "action": "RETRAIN",
                    "detail": f"volatility and stock models refitted on data up to {end.date()}"})
        # in-sample vs out-of-sample AUC of the gradient-boosting stress model (overfitting check)
        tr = selection._train_rows(P, f["y"], None, end)
        tr = tr[tr.reg == 1]
        te = P[(P.index.get_level_values("date").year == year)].dropna(subset=selection.COLS + ["y"])
        te = te[f["y"].reindex(te.index.get_level_values("date")).values == 1]
        if len(te) > 200 and "high" in gb:
            gb_auc.append({"Year": year, "GB in-sample AUC": roc_auc_score(tr.y, gb["high"].predict_proba(tr[selection.COLS])[:, 1]),
                           "GB out-of-sample AUC": roc_auc_score(te.y, gb["high"].predict_proba(te[selection.COLS])[:, 1]),
                           "LR out-of-sample AUC": roc_auc_score(te.y, lr["high"].predict_proba(te[selection.COLS])[:, 1])})
    scores["stress"] = pd.concat(stress).reindex(index=idx, columns=tick)
    scores["stress_gb"] = pd.concat(stress_gb).reindex(index=idx, columns=tick)
    reg = f["regime"].reindex(idx)

    def retrain(i, sc):
        """On a drawdown trigger: refit the stress model on the most recent two years only."""
        d = idx[i]
        start = nc.index[max(0, nc.index.get_loc(d) - 504)]
        m = selection.fit(P, f["y"], d, start=start)
        if "high" not in m:
            return "recent data too short to retrain; "
        new = selection.score(m, P, "high", idx[min(i + 1, len(idx) - 1)], f"{d.year}-12-31").reindex(columns=tick)
        sc["stress"].loc[new.index] = new.values
        return f"stress model refitted on {start.date()} to {d.date()}; "

    # 4. runs
    runs = {}
    def go(name, policy, dd=None, rt=False):
        r = portfolio.run(O, C, vol, copy.deepcopy(scores), reg, policy=policy, k=a.k, dd=dd, retrain_fn=retrain if rt else None)
        runs[name] = r
        print(f"  {name}: CAGR {stats(r.equity, None, None)['CAGR %']:.2f}%")
    print("Running portfolios ...")
    go("Regime switch (LR), no trigger", "regime_switch")
    for dd in (0.08, 0.10, 0.12):
        go(f"Regime switch (LR) + {dd:.0%} trigger", "regime_switch", dd, rt=True)
    go("Regime switch (GB), no trigger", "regime_switch_gb")
    go("Momentum only", "momentum")
    go("Stress model only", "stress")
    go("Low volatility only", "low_vol")
    go("Equal-weight NIFTY 50 (benchmark)", "equal_weight")
    bench = nc.reindex(idx).ffill()
    eqs = {n: r.equity for n, r in runs.items()} | {"NIFTY 50 buy and hold (benchmark)": bench / bench.iloc[0] * 1e6}

    # choose the drawdown threshold on the development period only
    dev = {dd: stats(runs[f"Regime switch (LR) + {dd:.0%} trigger"].equity, "2016", "2021")["Calmar"] for dd in (0.08, 0.10, 0.12)}
    best_dd = max(dev, key=dev.get)
    headline = f"Regime switch (LR) + {best_dd:.0%} trigger"

    # 5. tables
    tabs = {}
    for pname, (s, e) in PERIODS.items():
        t = pd.DataFrame({n: stats(eq, s, e, runs[n].turnover if n in runs else None) for n, eq in eqs.items()}).T
        t.index.name = "Approach"
        tabs[pname] = t
        t.to_csv(OUT / f"table_{pname.split()[0].lower()}.csv")
    # performance on days the forecast said rising/high
    stressed = reg.isin(["rising", "high"])
    sd = pd.DataFrame({n: {"Annualised return on forecast rising/high days %": eq.pct_change()[stressed].mean() * 252 * 100,
                           "Days": int(stressed.sum())} for n, eq in eqs.items()}).T
    sd.index.name = "Approach"

    # 6. overfitting flags
    ic_dev = selection.information_coefficient(P, f["y"], "2013-01-01", "2021-12-31", 1)
    ic_ho = selection.information_coefficient(P, f["y"], "2022-01-01", None, 1)
    ic = pd.DataFrame({"IC 2013–2021 (high-vol days)": ic_dev, "IC 2022+ (high-vol days)": ic_ho})
    ic["Flag"] = np.where((ic.iloc[:, 0].abs() >= 0.02) & ((np.sign(ic.iloc[:, 0]) != np.sign(ic.iloc[:, 1])) | (ic.iloc[:, 1].abs() < 0.005)),
                          "looked useful before 2022, failed after", "")
    ic.index.name = "Feature"
    auc = pd.DataFrame(gb_auc).set_index("Year")
    dd_tab = pd.DataFrame({f"{dd:.0%}": {"Calmar 2016–2021": dev[dd],
                                          "Calmar 2022+": stats(runs[f"Regime switch (LR) + {dd:.0%} trigger"].equity, "2022", None)["Calmar"],
                                          "Triggers": len(runs[f"Regime switch (LR) + {dd:.0%} trigger"].log)} for dd in (0.08, 0.10, 0.12)}).T
    dd_tab.index.name = "Trigger"
    flags = []
    if dd_tab["Calmar 2022+"].idxmax() != dd_tab["Calmar 2016–2021"].idxmax():
        flags.append(f"The best drawdown trigger before 2022 ({dd_tab['Calmar 2016–2021'].idxmax()}) was not the best after 2022 ({dd_tab['Calmar 2022+'].idxmax()}).")
    gap = (auc["GB in-sample AUC"] - auc["GB out-of-sample AUC"]).mean()
    if gap > 0.05:
        flags.append(f"Gradient boosting fits its training data much better than new data (average AUC gap {gap:.2f}): overfitting.")
    for feat in ic.index[ic.Flag != ""]:
        flags.append(f"Feature '{feat}' looked useful in high-volatility periods before 2022 but did not hold after.")
    imp_mean = pd.concat(imps).groupby(level=1).mean()

    # 7. audit log
    full_log = pd.concat([pd.DataFrame(log), runs[headline].log]).sort_values("date")
    full_log.to_csv(OUT / "audit_log_vs.csv", index=False)

    # 8. current state for the dashboard (latest model, latest close)
    last = idx[-1]
    lr = selection.fit(P, f["y"], pd.Timestamp(f"{last.year - 1}-12-31"))
    cur = P.xs(last, level="date").dropna(subset=selection.COLS)
    coef = selection.importance(lr)["high"]
    contrib = (cur[selection.COLS].values - 0.5) * coef.values
    reasons = [", ".join(f"{features.FEATURES[j]} {'+' if contrib[r, j] > 0 else '−'}" for j in np.argsort(-np.abs(contrib[r]))[:3])
               for r in range(len(cur))]
    rank = pd.DataFrame({"stress_score": lr["high"].predict_proba(cur[selection.COLS])[:, 1],
                         "momentum_120d_%": cur["mom_120"] * 100, "volatility_20d_%": cur["vol_20"] * 100,
                         "beta": cur["beta"], "defensive": cur["defensive"].astype(bool), "top_reasons": reasons}, index=cur.index)
    rank.sort_values("stress_score", ascending=False).to_csv(OUT / "current_ranking.csv")
    state = {"date": str(last.date()), "p_high": float(f["p_high"].iloc[-1]), "regime": f["regime"].iloc[-1],
             "vix": float(f["vix"].iloc[-1]), "rv20": float(f["rv20"].iloc[-1]), "headline": headline, "k": a.k}
    (OUT / "current_state.json").write_text(json.dumps(state, indent=1))
    pd.DataFrame(eqs).to_csv(OUT / "equity_curves.csv")
    f[["p_high", "regime", "vix", "rv20", "fwd_rv", "thr"]].loc["2016":].to_csv(OUT / "regime_forecast.csv")
    imp_mean.to_csv(OUT / "feature_importance.csv")

    # 9. five charts
    plt.rcParams.update({"figure.dpi": 130, "axes.spines.top": False, "axes.spines.right": False, "font.size": 9})
    show = [headline, "Equal-weight NIFTY 50 (benchmark)", "NIFTY 50 buy and hold (benchmark)"]
    colors = [C_BLUE, C_GOLD, C_GREY]
    fig, ax = plt.subplots(figsize=(10, 4.2))
    for n, c in zip(show, colors):
        ax.plot(eqs[n].index, eqs[n] / 1e5, color=c, lw=1.4, label=n)
    ax.set_yscale("log"); ax.axvline(SPLIT, color="k", ls=":", lw=0.8)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}"))
    ax.yaxis.set_minor_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}" if v in (15, 30, 60) else ""))
    ax.set_ylabel("Portfolio value (Rs lakh, log)"); ax.legend(frameon=False)
    ax.set_title("1. Walk-forward equity vs benchmarks (dotted line: start of hold-out)", loc="left")
    fig.tight_layout(); fig.savefig(OUT / "chart_1_equity.png"); plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 3.2))
    for n, c in zip(show, colors):
        ax.plot(eqs[n].index, drawdown(eqs[n]) * 100, color=c, lw=1.1, label=n)
    ax.set_ylabel("Drawdown %"); ax.legend(frameon=False, fontsize=8); ax.axvline(SPLIT, color="k", ls=":", lw=0.8)
    ax.set_title("2. Drawdown from peak", loc="left")
    fig.tight_layout(); fig.savefig(OUT / "chart_2_drawdown.png"); plt.close(fig)

    rf = f.loc["2016":]
    fig, ax = plt.subplots(figsize=(10, 3.4))
    ax.fill_between(rf.index, 0, rf["p_high"], color=C_RED, alpha=0.35, lw=0, label="Forecast probability of high volatility")
    ax2 = ax.twinx(); ax2.plot(rf.index, rf["fwd_rv"], color="k", lw=0.6, label="Actual NIFTY volatility, next 10 days (%)")
    ax.set_ylim(0, 1); ax.set_ylabel("Probability"); ax2.set_ylabel("Volatility %")
    ax.legend(loc="upper left", frameon=False, fontsize=8); ax2.legend(loc="upper right", frameon=False, fontsize=8)
    ax.set_title("3. Volatility regime forecast vs what happened", loc="left")
    fig.tight_layout(); fig.savefig(OUT / "chart_3_regime.png"); plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    imp = imp_mean.sort_values("high")
    yy = np.arange(len(imp))
    ax.barh(yy - 0.2, imp["calm"], 0.4, color=C_GREY, label="Calm regime")
    ax.barh(yy + 0.2, imp["high"], 0.4, color=C_BLUE, label="High-volatility regime")
    ax.set_yticks(yy, imp.index); ax.axvline(0, color="k", lw=0.8); ax.legend(frameon=False)
    ax.set_xlabel("Average standardised coefficient, 2016–2026 models (+ helps a stock beat NIFTY)")
    ax.set_title("4. Which indicators matter in which regime", loc="left")
    fig.tight_layout(); fig.savefig(OUT / "chart_4_importance.png"); plt.close(fig)

    crisis = pd.DataFrame({p: {n: stats(eqs[n], *PERIODS[p]).get("Period return %", np.nan) for n in show}
                           for p in ["COVID crash (14 Feb–30 Apr 2020)", "2022 sell-off (Jan–Jun 2022)"]})
    fig, ax = plt.subplots(figsize=(8, 3.4))
    crisis.T.plot.bar(ax=ax, color=colors, rot=0, width=0.75)
    ax.axhline(0, color="k", lw=0.8); ax.set_ylabel("Return over the period %"); ax.legend(frameon=False, fontsize=8)
    ax.set_title("5. High-volatility periods", loc="left")
    fig.tight_layout(); fig.savefig(OUT / "chart_5_crisis.png"); plt.close(fig)

    # 10. report
    cols = ["CAGR %", "Sharpe", "Max drawdown %", "Worst day %", "Days below -2% (count)", "Calmar", "Turnover (x/yr)"]
    rep = ["# Volatility-aware NIFTY 50 stock selection: walk-forward results\n",
           "**Academic research prototype. Not investment advice.** Past backtest results do not predict future returns.\n",
           f"{len(prices)} current NIFTY 50 stocks, data to {last.date()}. Models refitted every 1 January on past data only. "
           f"Weekly rebalance, top {a.k}, inverse-volatility weights, 0.15% cost per side, signals at the close, fills at the next open. "
           f"Drawdown trigger chosen on 2016–2021 Calmar only: {best_dd:.0%}.\n"]
    for pname in PERIODS:
        c = [x for x in cols if x in tabs[pname].columns] + (["Period return %"] if "Period return %" in tabs[pname].columns else [])
        rep += [f"## {pname}\n", md(tabs[pname][c]), ""]
    rep += ["## Days the forecast said rising or high\n", md(sd, "{:.1f}"), ""]
    rep += ["## Volatility forecast accuracy (high = p ≥ 0.5 vs naive 'next 10 days like the last 10')\n"]
    for lab, r in acc.items():
        rep += [f"**{lab}:** {r['days']} days, {r['share_high']:.0%} actually high. Hit rate {r['hit_rate']:.1%} "
                f"(naive {r['naive_hit_rate']:.1%}); precision {r['precision']:.1%}; recall {r['recall']:.1%} (naive {r['naive_recall']:.1%}).\n",
                md(r["confusion"].rename(index={0: "actual not high", 1: "actual high"}, columns={0: "forecast not high", 1: "forecast high"}), "{:.0f}"), ""]
    rep += ["## Drawdown trigger thresholds\n", md(dd_tab), "", "## Overfitting checks\n",
            "Feature information coefficients on high-volatility days:\n", md(ic.round(3), "{:.3f}"), "",
            "Gradient boosting vs logistic regression (stress model):\n", md(auc.round(3), "{:.3f}"), "",
            "**Flags:**\n", *([f"- {x}" for x in flags] or ["- none"]), "",
            "## Limitations\n",
            "- Survivorship bias: today's NIFTY 50 list is used for all years; no free point-in-time constituent list exists. This flatters every approach that holds these stocks, including the equal-weight benchmark.\n"
            "- Yahoo Finance data is unofficial; VIX futures term structure was not available and is not used.\n"
            "- Daily data only; the drawdown trigger acts at the next open.\n"
            "- One market, one decade: 2022 onward is a short hold-out.\n"
            "- Long-only cash segment; no shorting or derivatives hedges.\n",
            "## Compliance\n",
            "Offering stock selections to customers requires SEBI Research Analyst registration, and running the algorithm for clients requires exchange empanelment through a broker and algo registration. This prototype is not offered to anyone.\n"]
    (OUT / "report.md").write_text("\n".join(rep), encoding="utf-8")
    print(md(tabs["Full walk-forward 2016–2026"][cols]))
    print(md(tabs["Hold-out 2022–2026"][cols]))
    print("flags:", flags)
    print("Done:", OUT)


if __name__ == "__main__":
    main()
