"""Run every experiment and write tables, charts and a markdown report to results/.

    python run.py --download      # first time: fetch NSE data (needs internet)
    python run.py                 # run experiments on real data
    python run.py --demo          # run on synthetic data (offline pipeline test only)
"""
from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from algoguard import data, v2
from algoguard.backtest import run_backtest
from algoguard.metrics import drawdown, summarize
from algoguard.risk import GUARDED, RAW, RULE_LABELS, RULES, only, without
from algoguard.strategies import STRATEGIES, build_signals, ema_crossover

RAW_C, GRD_C, BMK_C, GRID_C = "#B4483C", "#1F6F8B", "#8A8A8A", "#DADADA"
plt.rcParams.update({"figure.dpi": 130, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": GRID_C, "grid.linewidth": 0.6, "font.size": 9})

KEY = ["CAGR %", "Sharpe", "Max drawdown %", "Worst day %", "Days below -2% (count)", "Calmar", "Trades", "Avg exposure %"]


def md_table(df: pd.DataFrame, floatfmt="{:.2f}") -> str:
    cols = [df.index.name or ""] + list(df.columns)
    header = "| " + " | ".join(map(str, cols)) + " |"
    lines = [header, "|" + "---|" * (header.count(" | ") + 1)]
    for idx, row in df.iterrows():
        cells = [floatfmt.format(v) if isinstance(v, (float, np.floating)) else str(v) for v in row.values]
        lines.append("| " + " | ".join([str(idx)] + cells) + " |")
    return "\n".join(lines)


def period(equity, start=None, end=None):
    e = equity.loc[start:end]
    return e / e.iloc[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--download", action="store_true")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--force", action="store_true", help="re-download even if cached")
    ap.add_argument("--out", default="results")
    ap.add_argument("--split", default="2022-01-01", help="out-of-sample start date")
    a = ap.parse_args()

    if a.download:
        print("Downloading NSE data via yfinance ...")
        data.download(force=a.force)
    if a.demo:
        prices, vix, index = data.make_synthetic()
        tag = "SYNTHETIC DEMO DATA (not market results)"
    else:
        prices, vix, index = data.load_real()
        tag = "NSE daily data via Yahoo Finance"
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    dates = next(iter(prices.values())).index
    split = pd.Timestamp(a.split)
    if split <= dates[0] or split >= dates[-1]:
        split = dates[int(len(dates) * 0.7)]
    print(f"Data: {len(prices)} stocks, {dates[0].date()} to {dates[-1].date()} ({len(dates)} sessions). {tag}")

    report = [f"# AlgoGuard results\n\nData: {tag}. {len(prices)} stocks, {dates[0].date()} to {dates[-1].date()}, "
              f"{len(dates)} sessions. Capital Rs 10 lakh, costs 0.15% per side, signals at close, fills next open.\n"]

    bench, bench_name = None, "NIFTY 50 buy & hold"
    if index is not None and "close" in index and index["close"].notna().mean() > 0.9:
        b = index["close"].ffill().bfill()
        bench = 1_000_000 * b / b.iloc[0]
    else:
        # fallback: equal-weight buy & hold of the same stocks
        closes = pd.DataFrame({s: df["close"] for s, df in prices.items()})
        bench = 1_000_000 * (closes / closes.iloc[0]).mean(axis=1)
        bench_name = "Equal-weight buy & hold"
        print("  NIFTY data unusable; using equal-weight buy & hold of the stocks as benchmark")

    # ---------------- 1. Main comparison -------------------------------------------------
    rows, results, signals = {}, {}, {}
    for name, fn in STRATEGIES.items():
        sig = build_signals(prices, fn)
        signals[name] = sig
        for label, cfg in (("Raw", RAW), ("Guarded", GUARDED)):
            r = run_backtest(prices, sig, vix, cfg)
            results[(name, label)] = r
            rows[f"{name} | {label}"] = summarize(r.equity, r.trades, r.exposure)
            r.trades.to_csv(out / f"trades_{name.split()[0].lower()}_{label.lower()}.csv", index=False)
            if label == "Guarded":
                r.events.to_csv(out / f"audit_log_{name.split()[0].lower()}.csv", index=False)
    if bench is not None:
        rows[bench_name] = summarize(bench)
    main_tbl = pd.DataFrame(rows).T
    main_tbl.index.name = "Strategy | risk layer"
    main_tbl.to_csv(out / "1_main_comparison.csv")
    report += ["## 1. Raw strategy vs strategy + guardrails\n", md_table(main_tbl[[c for c in KEY if c in main_tbl]]), ""]
    print("\n", main_tbl[[c for c in KEY if c in main_tbl]].round(2).to_string())

    # charts: equity + underwater per strategy
    fig, axes = plt.subplots(2, len(STRATEGIES), figsize=(5 * len(STRATEGIES), 6), sharex=True,
                             gridspec_kw={"height_ratios": [2.2, 1]})
    for k, name in enumerate(STRATEGIES):
        ax, ax2 = axes[0, k], axes[1, k]
        for label, col in (("Raw", RAW_C), ("Guarded", GRD_C)):
            e = results[(name, label)].equity
            ax.plot(e.index, e / 1e5, color=col, lw=1.3, label=label)
            if label == "Raw":
                ax2.fill_between(e.index, drawdown(e) * 100, 0, color=col, alpha=0.25, lw=0)
            else:
                ax2.plot(e.index, drawdown(e) * 100, color=col, lw=1)
        if bench is not None:
            ax.plot(bench.index, bench / 1e5, color=BMK_C, lw=1, ls="--", label=bench_name.replace(" buy & hold", ""))
        ax.axvline(split, color="k", lw=0.8, ls=":")
        ax.set_yscale("log")
        ax.set_title(name, fontsize=10, loc="left")
        ax.set_ylabel("Portfolio value (Rs lakh, log)") if k == 0 else None
        ax2.set_ylabel("Drawdown %") if k == 0 else None
        if k == 0:
            ax.legend(frameon=False, fontsize=8)
    fig.suptitle("Equity and drawdown: raw strategy vs guarded (dotted line = out-of-sample start)", x=0.01, ha="left", fontsize=11)
    fig.tight_layout()
    fig.savefig(out / "chart_1_equity_drawdown.png")
    plt.close(fig)

    # ---------------- 2. In-sample vs out-of-sample --------------------------------------
    rows = {}
    for (name, label), r in results.items():
        for pname, (s, e) in {"In-sample": (None, split - pd.Timedelta(days=1)), "Out-of-sample": (split, None)}.items():
            rows[f"{name} | {label} | {pname}"] = summarize(period(r.equity, s, e) * 1e6)
    oos = pd.DataFrame(rows).T[["CAGR %", "Sharpe", "Max drawdown %", "Worst day %"]]
    oos.index.name = "Strategy | layer | period"
    oos.to_csv(out / "2_in_vs_out_of_sample.csv")
    report += [f"## 2. In-sample vs out-of-sample (split {split.date()})\n",
               "All parameters are textbook defaults fixed before testing, so the out-of-sample period is a genuine hold-out.\n",
               md_table(oos), ""]

    # ---------------- 3. Ablation: which rule does the work? -----------------------------
    rows = {}
    for name in STRATEGIES:
        sig = signals[name]
        base = summarize(results[(name, "Raw")].equity)
        for rule in RULES:
            r1 = run_backtest(prices, sig, vix, only(rule))
            m1 = summarize(r1.equity)
            r2 = run_backtest(prices, sig, vix, without(rule) if rule != "vol_target" else replace(GUARDED, vol_target=None))
            m2 = summarize(r2.equity)
            rows[(name, RULE_LABELS[rule])] = {
                "Only this rule: Sharpe": m1["Sharpe"], "Only this rule: Max DD %": m1["Max drawdown %"],
                "Max DD change vs raw (pts)": m1["Max drawdown %"] - base["Max drawdown %"],
                "All rules except this: Sharpe": m2["Sharpe"], "All except this: Max DD %": m2["Max drawdown %"],
            }
    abl = pd.DataFrame(rows).T
    abl.index.names = ["Strategy", "Rule"]
    abl.to_csv(out / "3_ablation.csv")
    abl_md = abl.copy()
    abl_md.index = [f"{s} | {r}" for s, r in abl.index]
    abl_md.index.name = "Strategy | rule"
    report += ["## 3. Ablation: contribution of each rule\n",
               "Each rule switched on alone (vs raw), and each rule removed from the full set.\n", md_table(abl_md), ""]

    fig, ax = plt.subplots(figsize=(8, 3.6))
    piv = abl["Max DD change vs raw (pts)"].unstack(0)
    piv.plot.barh(ax=ax, color=["#1F6F8B", "#7FA7B5", "#C9A227"], width=0.75)
    ax.axvline(0, color="k", lw=0.8)
    ax.set_xlabel("Change in max drawdown vs raw strategy (percentage points, positive = shallower)")
    ax.set_ylabel("")
    ax.legend(frameon=False, fontsize=7)
    ax.set_title("Which guardrail reduces drawdown? (each rule on its own)", loc="left", fontsize=10)
    fig.tight_layout()
    fig.savefig(out / "chart_2_ablation.png")
    plt.close(fig)

    # ---------------- 4. Parameter robustness (EMA grid) ---------------------------------
    fasts, slows = [10, 20, 30, 50], [50, 100, 150, 200]
    grid = {lab: np.full((len(fasts), len(slows)), np.nan) for lab in ("Raw", "Guarded")}
    dd = {lab: np.full((len(fasts), len(slows)), np.nan) for lab in ("Raw", "Guarded")}
    for i, f in enumerate(fasts):
        for j, s in enumerate(slows):
            if f >= s:
                continue
            sig = build_signals(prices, ema_crossover, fast=f, slow=s)
            for lab, cfg in (("Raw", RAW), ("Guarded", GUARDED)):
                m = summarize(run_backtest(prices, sig, vix, cfg).equity)
                grid[lab][i, j], dd[lab][i, j] = m["Sharpe"], m["Max drawdown %"]
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.6))
    vmax = np.nanmax(np.abs(np.concatenate([grid["Raw"], grid["Guarded"]])))
    for ax, lab in zip(axes, ("Raw", "Guarded")):
        im = ax.imshow(grid[lab], cmap="RdBu", vmin=-vmax, vmax=vmax)
        for i in range(len(fasts)):
            for j in range(len(slows)):
                if not np.isnan(grid[lab][i, j]):
                    ax.text(j, i, f"{grid[lab][i, j]:.2f}\n({dd[lab][i, j]:.0f}%)", ha="center", va="center", fontsize=7)
        ax.set_xticks(range(len(slows)), slows)
        ax.set_yticks(range(len(fasts)), fasts)
        ax.set_xlabel("Slow EMA")
        ax.set_ylabel("Fast EMA")
        ax.set_title(f"{lab}: Sharpe (max drawdown)", loc="left", fontsize=10)
        ax.grid(False)
    fig.colorbar(im, ax=axes, shrink=0.8)
    fig.savefig(out / "chart_3_robustness_grid.png", bbox_inches="tight")
    plt.close(fig)
    rob = pd.DataFrame({f"{lab} {what}": arr[~np.isnan(arr)] for lab in ("Raw", "Guarded")
                        for what, arr in (("Sharpe", grid[lab]), ("MaxDD %", dd[lab]))})
    rob_s = rob.describe().loc[["mean", "min", "max"]]
    rob_s.index.name = "Across 10 EMA settings"
    report += ["## 4. Parameter robustness (EMA crossover, 10 settings)\n",
               "Guardrails should help across settings, not just at one lucky parameter choice.\n", md_table(rob_s), ""]

    # ---------------- 5. Cost sensitivity --------------------------------------------------
    rows = {}
    for name in STRATEGIES:
        for c in (0.0005, 0.0015, 0.003):
            for lab, cfg in (("Raw", RAW), ("Guarded", GUARDED)):
                rows[f"{name} | {lab} | {c:.2%}"] = summarize(run_backtest(prices, signals[name], vix, cfg, cost_rate=c).equity)
    cost = pd.DataFrame(rows).T[["CAGR %", "Sharpe", "Max drawdown %"]]
    cost.index.name = "Strategy | layer | cost per side"
    cost.to_csv(out / "5_cost_sensitivity.csv")
    report += ["## 5. Transaction-cost sensitivity\n", md_table(cost), ""]

    # ---------------- 6. Guardrail activity -----------------------------------------------
    rows = {}
    for name in STRATEGIES:
        r = results[(name, "Guarded")]
        ev = r.events
        stops = (r.trades.exit_reason == "risk: ATR stop").sum() if len(r.trades) else 0
        rows[name] = {"ATR stops hit": stops, "Halts (drawdown)": int(ev.action.isin(["HALT + FLATTEN", "HALT"]).sum()),
                      "Daily-loss cooldowns": int((ev.action == "COOLDOWN").sum()),
                      "Losing-streak pauses": int((ev.action == "PAUSE").sum()),
                      **{f"Entries blocked: {RULE_LABELS[k]}": v for k, v in r.blocked.items()}}
    act = pd.DataFrame(rows).T.fillna(0).astype(int)
    act.index.name = "Strategy"
    act.to_csv(out / "6_guardrail_activity.csv")
    report += ["## 6. How often the guardrails intervened\n",
               "Every intervention is in the audit log CSVs (date, rule, action, detail).\n", md_table(act, "{:.0f}"), ""]

    # ---------------- 7. Guarded v2: strategy-aware guardrails ---------------------------
    print(f"\nv2: choosing per-strategy guardrails on data before {split.date()} only ...")
    chosen, rows, menus = {}, {}, []
    for name in STRATEGIES:
        cfg2, menu_tbl = v2.select(prices, signals[name], vix, split)
        chosen[name] = cfg2
        menu_tbl.insert(0, "Strategy", name)
        menus.append(menu_tbl)
        r2 = run_backtest(prices, signals[name], vix, cfg2)
        results[(name, "Guarded v2")] = r2
        r2.events.to_csv(out / f"audit_log_{name.split()[0].lower()}_v2.csv", index=False)
        for label in ("Raw", "Guarded", "Guarded v2"):
            r = results[(name, label)]
            for pname, (s0, e0) in {"In-sample": (None, split - pd.Timedelta(days=1)), "Out-of-sample": (split, None)}.items():
                m = summarize(period(r.equity, s0, e0) * 1e6)
                rows[f"{name} | {label.replace('Guarded', 'Guarded v1') if label == 'Guarded' else label} | {pname}"] = m
    pd.concat(menus).to_csv(out / "7_v2_candidates_in_sample.csv", index=False)
    (out / "7_v2_chosen_settings.txt").write_text(
        f"Chosen on data before {split.date()} only (highest in-sample Calmar):\n"
        + "\n".join(f"{n}: {v2.describe(c)}" for n, c in chosen.items()) + "\n", encoding="utf-8")
    (out / "7_v2_chosen_settings.json").write_text(json.dumps(
        {"split": str(split.date()), "settings": {n: {k: getattr(c, k) for k in v2.MENU} for n, c in chosen.items()}},
        indent=2), encoding="utf-8")
    v2_tbl = pd.DataFrame(rows).T[["CAGR %", "Sharpe", "Max drawdown %", "Worst day %", "Days below -2% (count)", "Calmar"]]
    v2_tbl.index.name = "Strategy | layer | period"
    v2_tbl.to_csv(out / "7_v2_comparison.csv")
    if bench is not None:
        for pname, (s0, e0) in {"In-sample": (None, split - pd.Timedelta(days=1)), "Out-of-sample": (split, None)}.items():
            v2_tbl.loc[f"{bench_name} | {pname}"] = pd.Series(summarize(period(bench, s0, e0) * 1e6))[v2_tbl.columns]
    report += ["## 7. Guarded v2: strategy-aware guardrails\n",
               f"Each strategy picks its own drawdown-breaker mode, VIX filter and stop distance from a fixed menu of "
               f"16 settings. The choice is made by highest Calmar on data before {split.date()} only, then run once on "
               f"the out-of-sample period. All other rules are unchanged from v1.\n",
               "Chosen settings:\n", *[f"- {n}: {v2.describe(c)}" for n, c in chosen.items()], "",
               md_table(v2_tbl), "",
               "Every candidate's in-sample score is in `7_v2_candidates_in_sample.csv`.\n"]
    print(v2_tbl.round(2).to_string())

    fig, axes = plt.subplots(1, len(STRATEGIES), figsize=(5 * len(STRATEGIES), 3.4), sharey=True)
    labels = ["Raw", "Guarded v1", "Guarded v2"]
    cols_ = [RAW_C, "#7FA7B5", GRD_C]
    for ax, name in zip(axes, STRATEGIES):
        x = np.arange(2)
        for k, (lab, col) in enumerate(zip(labels, cols_)):
            vals = [v2_tbl.loc[f"{name} | {lab} | {p}", "Max drawdown %"] for p in ("In-sample", "Out-of-sample")]
            ax.bar(x + (k - 1) * 0.26, vals, 0.24, color=col, label=lab)
        ax.set_xticks(x, ["In-sample\n(used to choose v2)", "Out-of-sample\n(2022 onward)"])
        ax.set_title(name, loc="left", fontsize=10)
        ax.axhline(0, color="k", lw=0.8)
    axes[0].set_ylabel("Max drawdown %")
    axes[0].legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(out / "chart_4_v2_drawdown.png")
    plt.close(fig)

    report += ["## Limitations\n",
               "- Survivorship bias: the universe is today's large caps, tested back to 2012.\n"
               "- Daily bars: the daily-loss rule acts at the next open, not intraday. Intraday enforcement needs tick or minute data.\n"
               "- Stops fill at the stop price unless the open gaps through it; real slippage in fast markets can be worse.\n"
               "- Yahoo Finance data is unofficial; corporate-action adjustments can contain errors.\n"
               "- Long-only, cash segment. F&O (where SEBI found most retail losses) is the natural next step.\n"]
    (out / "report.md").write_text("\n".join(report), encoding="utf-8")
    print(f"\nDone. Tables, charts, audit logs and report.md written to {out.resolve()}")


if __name__ == "__main__":
    main()
