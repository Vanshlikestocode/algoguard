"""AlgoGuard live dashboard.   streamlit run app.py"""
from __future__ import annotations

import json
import os
from datetime import datetime
from dataclasses import replace
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from algoguard import data
from algoguard.backtest import run_backtest
from algoguard.metrics import drawdown, summarize
from algoguard import commitment
from algoguard.risk import GUARDED, PROFILES, RAW, RULE_LABELS
from algoguard.strategies import STRATEGIES, build_signals

RAW_C, GRD_C, BMK_C = "#B4483C", "#1F6F8B", "#8A8A8A"
st.set_page_config(page_title="AlgoGuard", layout="wide")


@st.cache_data(show_spinner="Loading market data ...")
def load(demo: bool):
    if demo:
        return data.make_synthetic()
    return data.load_real()


@st.cache_data(show_spinner=False)
def signals_for(demo: bool, strategy: str):
    prices, _, _ = load(demo)
    return build_signals(prices, STRATEGIES[strategy])


# On Streamlit Community Cloud the app runs from /mount/src/... and is shared by every visitor,
# so the commitment lock lives in each visitor's browser session instead of one shared file.
HOSTED = Path(__file__).resolve().as_posix().startswith("/mount/src/") or os.environ.get("ALGOGUARD_HOSTED") == "1"


def load_lock():
    return st.session_state.get("lock_state") if HOSTED else commitment.load()


def save_lock(state):
    if HOSTED:
        st.session_state["lock_state"] = state
    else:
        commitment.save(state)


has_real = any(data.DATA_DIR.glob("*.NS.csv"))
with st.sidebar:
    st.title("AlgoGuard")
    st.caption("Rule-based algo trading with an enforceable risk layer")
    demo = st.toggle("Use synthetic demo data", value=not has_real,
                     help="Real data: run `python run.py --download` once.")
    strategy = st.selectbox("Strategy", list(STRATEGIES))
    capital = st.number_input("Capital (Rs)", 100_000, 100_000_000, 1_000_000, step=100_000)
    cost = st.slider("Cost per side (%)", 0.0, 0.5, 0.15, 0.01) / 100

    st.subheader("Guardrails")
    v2_file = Path(__file__).resolve().parent / "results" / "7_v2_chosen_settings.json"
    v2_sets = json.loads(v2_file.read_text())["settings"] if v2_file.exists() else {}
    saved = None if demo else load_lock()
    saved_c = (saved or {}).get("committed", {})
    starts = {}
    # Offer "My locked rules" only when a session OPENS with a lock on (e.g. after a reload). Adding the
    # option mid-session would reset every control and swallow the user's next click.
    if "open_with_lock" not in st.session_state:
        st.session_state["open_with_lock"] = bool(saved_c.get("lock_enabled"))
    if st.session_state["open_with_lock"] and saved_c:
        starts["My locked rules"] = replace(GUARDED, **{f: v for f, v in saved_c.items() if f not in ("lock_enabled", "wait_hours")})
    starts |= {"Conservative": PROFILES["Conservative"],
              "Balanced (v1 defaults)": PROFILES["Balanced"],
              "Aggressive": PROFILES["Aggressive"]}
    if strategy in v2_sets and not demo:
        starts["v2 for this strategy (chosen on pre-2022 data)"] = replace(GUARDED, **v2_sets[strategy])
    preset = st.radio("Start from", list(starts), index=0 if "My locked rules" in starts else 1,
                      help="Risk profiles are hand-picked starting points, not tuned. Adjust any rule below.")
    g = starts[preset]
    k = preset.split()[0]  # new widget keys per preset, so picking one resets the controls
    stop_on = st.checkbox("ATR stop-loss", g.stop_atr_mult is not None, key=f"stop_{k}")
    stop_k = st.slider("Stop distance (x ATR)", 1.0, 6.0, g.stop_atr_mult or GUARDED.stop_atr_mult, 0.5, disabled=not stop_on, key=f"stopk_{k}")
    dl_on = st.checkbox("Daily loss limit", g.daily_loss_limit is not None, key=f"dl_{k}")
    dl = st.slider("Max portfolio loss in a day (%)", 0.5, 5.0, (g.daily_loss_limit or GUARDED.daily_loss_limit) * 100, 0.25, disabled=not dl_on, key=f"dlv_{k}") / 100
    dl_cd = st.slider("Cooldown after breach (sessions)", 1, 10, g.daily_loss_cooldown, disabled=not dl_on, key=f"dlc_{k}")
    cl_on = st.checkbox("Losing-streak cooldown", g.consec_loss_limit is not None, key=f"cl_{k}")
    cl = st.slider("Losing trades in a row", 2, 8, g.consec_loss_limit or GUARDED.consec_loss_limit, disabled=not cl_on, key=f"clv_{k}")
    cl_cd = st.slider("Pause length (sessions)", 1, 20, g.consec_loss_cooldown, disabled=not cl_on, key=f"clc_{k}")
    dd_on = st.checkbox("Drawdown circuit breaker", g.max_drawdown is not None, key=f"dd_{k}")
    dd = st.slider("Halt at drawdown (%)", 5, 40, int(round((g.max_drawdown or GUARDED.max_drawdown) * 100)), disabled=not dd_on, key=f"ddv_{k}") / 100
    dd_days = st.slider("Halt length (sessions)", 5, 60, g.dd_halt_days, disabled=not dd_on, key=f"ddd_{k}")
    dd_flat = st.checkbox("Breaker sells everything (off = only block new entries)", g.dd_flatten, disabled=not dd_on, key=f"ddf_{k}")
    vix_on = st.checkbox("India VIX filter", g.vix_limit is not None, key=f"vix_{k}")
    vix_lim = st.slider("No new entries when VIX above", 12.0, 45.0, g.vix_limit or GUARDED.vix_limit, 0.5, disabled=not vix_on, key=f"vixl_{k}")
    vt_on = st.checkbox("Volatility-scaled sizing", g.vol_target is not None, key=f"vt_{k}")
    vt = st.slider("Target volatility per position (%)", 10, 50, int(round((g.vol_target or GUARDED.vol_target) * 100)), disabled=not vt_on, key=f"vtv_{k}") / 100
    cap = st.slider("Max size of one position (%)", 5, 50, int(round(g.max_position_pct * 100)), key=f"cap_{k}") / 100

    st.subheader("Commitment lock")
    lock_on = st.toggle("Lock my rules", bool(saved_c.get("lock_enabled")), help="Tightening a rule applies at once. Loosening one, or "
                        "switching the lock off, only applies after the waiting period.")
    waits = {"1 minute (demo)": 1 / 60, "1 hour": 1.0, "24 hours": 24.0, "7 days": 168.0}
    saved_wait = next((lbl for lbl, h in waits.items() if abs(h - saved_c.get("wait_hours", 24.0)) < 1e-9), "24 hours")
    wait_lbl = st.select_slider("Waiting period for loosening", list(waits), value=saved_wait)
    if HOSTED:
        st.caption("Web version: your lock lasts for this browser session. Run the app locally to keep it across restarts.")

requested = {"stop_atr_mult": stop_k if stop_on else None,
             "daily_loss_limit": dl if dl_on else None, "daily_loss_cooldown": dl_cd,
             "consec_loss_limit": cl if cl_on else None, "consec_loss_cooldown": cl_cd,
             "max_drawdown": dd if dd_on else None, "dd_halt_days": dd_days, "dd_flatten": dd_flat,
             "vix_limit": vix_lim if vix_on else None,
             "vol_target": vt if vt_on else None, "max_position_pct": cap,
             "lock_enabled": lock_on, "wait_hours": waits[wait_lbl]}
lock_state, effective = commitment.reconcile(load_lock(), requested, datetime.now())
if not demo:
    save_lock(lock_state)
cfg = replace(GUARDED, **{f: v for f, v in effective.items() if f not in ("lock_enabled", "wait_hours")})

try:
    prices, vix, index = load(demo)
except FileNotFoundError as e:
    st.error(str(e))
    st.stop()
sig = signals_for(demo, strategy)
raw = run_backtest(prices, sig, vix, RAW, capital, cost)
grd = run_backtest(prices, sig, vix, cfg, capital, cost)

dates = sig.index
lo, hi = st.select_slider("Period", options=list(dates.date), value=(dates[0].date(), dates[-1].date()))
sl = slice(pd.Timestamp(lo), pd.Timestamp(hi))
e_raw = raw.equity.loc[sl] / raw.equity.loc[sl].iloc[0] * capital
e_grd = grd.equity.loc[sl] / grd.equity.loc[sl].iloc[0] * capital

if demo:
    st.warning("Synthetic demo data: these numbers are not market results.")
def fmt(f, v):
    if v is None:
        return "off"
    if isinstance(v, bool):
        return "on" if v else "off"
    if f in ("daily_loss_limit", "max_drawdown", "vol_target", "max_position_pct"):
        return f"{v:.2%}".replace(".00%", "%")
    if f == "stop_atr_mult":
        return f"{v:g}x ATR"
    if f == "wait_hours":
        return next((lbl for lbl, h in waits.items() if abs(h - v) < 1e-9), f"{v:g} h")
    return f"{v:g}"


pend = lock_state["pending"]
if pend:
    st.warning("**Commitment lock: these loosenings are waiting.** The backtest below uses your committed rules until then.\n\n"
               + "\n".join(f"- {commitment.LABELS.get(f, f)}: {fmt(f, effective[f])} → {fmt(f, p['value'])}, "
                            f"applies {datetime.fromisoformat(p['effective_at']):%d %b %H:%M}" for f, p in pend.items()))
elif effective.get("lock_enabled"):
    st.info(f"Rules locked. Tightening applies at once; loosening waits {fmt('wait_hours', effective['wait_hours'])}.")

st.subheader(f"{strategy}: raw vs guarded")
m_raw, m_grd = summarize(e_raw), summarize(e_grd)
cols = st.columns(5)
for c, k, better_low in zip(cols, ["CAGR %", "Sharpe", "Max drawdown %", "Worst day %", "Days below -2% (count)"],
                            [False, False, False, False, True]):
    d = m_grd[k] - m_raw[k]
    c.metric(k, f"{m_grd[k]:.2f}" if "count" not in k else f"{m_grd[k]:.0f}",
             f"{d:+.2f} vs raw" if "count" not in k else f"{d:+.0f} vs raw",
             delta_color="inverse" if better_low else "normal")

fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.68, 0.32], vertical_spacing=0.04)
fig.add_trace(go.Scatter(x=e_raw.index, y=e_raw, name="Raw", line=dict(color=RAW_C, width=1.5)), 1, 1)
fig.add_trace(go.Scatter(x=e_grd.index, y=e_grd, name="Guarded", line=dict(color=GRD_C, width=1.5)), 1, 1)
if index is not None and "close" in index and index["close"].notna().mean() > 0.9:
    b = index["close"].loc[sl]
    fig.add_trace(go.Scatter(x=b.index, y=b / b.iloc[0] * capital, name="NIFTY 50",
                             line=dict(color=BMK_C, width=1, dash="dash")), 1, 1)
fig.add_trace(go.Scatter(x=e_raw.index, y=drawdown(e_raw) * 100, name="Raw drawdown", fill="tozeroy",
                         line=dict(color=RAW_C, width=0.5), opacity=0.4, showlegend=False), 2, 1)
fig.add_trace(go.Scatter(x=e_grd.index, y=drawdown(e_grd) * 100, name="Guarded drawdown",
                         line=dict(color=GRD_C, width=1.2), showlegend=False), 2, 1)
halts = grd.events[grd.events.action.isin(["HALT + FLATTEN", "HALT"])]
for d0 in halts.date:
    if sl.start <= d0 <= sl.stop:
        fig.add_vline(x=d0, line=dict(color=GRD_C, width=0.6, dash="dot"))
fig.update_yaxes(title_text="Portfolio value (Rs)", row=1, col=1)
fig.update_yaxes(title_text="Drawdown %", row=2, col=1)
fig.update_layout(height=560, margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h", y=1.04),
                  hovermode="x unified")
st.plotly_chart(fig, use_container_width=True)

t1, t5, t2, t3, t4 = st.tabs(["Full metrics", "Before vs after 2022", "Audit log", "Trades", "Rule activity"])
with t5:
    split = pd.Timestamp("2022-01-01")
    rows = {}
    for lab, r in (("Raw", raw), ("Guarded", grd)):
        for per, (a, b) in {"Before 2022": (None, split - pd.Timedelta(days=1)), "2022 onward": (split, None)}.items():
            e = r.equity.loc[a:b]
            rows[(lab, per)] = summarize(e / e.iloc[0] * capital)
    hold = pd.DataFrame(rows).T[["CAGR %", "Sharpe", "Max drawdown %", "Worst day %", "Calmar"]]
    hold.index.names = ["Layer", "Period"]
    st.caption("Tuning the sliders until the chart looks good fits them to the past. Judge your settings on "
               "2022 onward: if they only shine before 2022, they will probably not hold up.")
    st.dataframe(hold.style.format("{:.2f}"), use_container_width=True)
    d_in = hold.loc[("Guarded", "Before 2022"), "Calmar"] - hold.loc[("Raw", "Before 2022"), "Calmar"]
    d_out = hold.loc[("Guarded", "2022 onward"), "Calmar"] - hold.loc[("Raw", "2022 onward"), "Calmar"]
    verdict = ("helps in both periods" if d_in > 0 and d_out > 0 else
               "helps only before 2022, so it may be fitted to the past" if d_in > 0 else
               "helps only from 2022" if d_out > 0 else "does not beat raw in either period")
    st.markdown(f"**Guarded vs raw on Calmar:** {d_in:+.2f} before 2022, {d_out:+.2f} from 2022. This setup {verdict}.")
with t1:
    full = pd.DataFrame({"Raw": summarize(e_raw, raw.trades, raw.exposure.loc[sl]),
                         "Guarded": summarize(e_grd, grd.trades, grd.exposure.loc[sl])})
    st.dataframe(full.style.format("{:.2f}"), use_container_width=True)
with t2:
    ev = grd.events[(grd.events.date >= sl.start) & (grd.events.date <= sl.stop)].copy()
    ev["rule"] = ev["rule"].map(RULE_LABELS).fillna(ev["rule"])
    rules = st.multiselect("Rules", sorted(ev.rule.unique()), default=sorted(ev.rule.unique()))
    st.caption("Every time the risk layer blocked, paused, halted or re-armed, with the reason.")
    st.dataframe(ev[ev.rule.isin(rules)].sort_values("date", ascending=False), use_container_width=True, height=380)
with t3:
    tr = grd.trades
    if len(tr):
        tr = tr[(tr.exit_date >= sl.start) & (tr.entry_date <= sl.stop)]
    st.dataframe(tr, use_container_width=True, height=380)
with t4:
    act = {RULE_LABELS.get(k, k): v for k, v in grd.blocked.items()}
    if len(grd.trades):
        act["ATR stops hit"] = int((grd.trades.exit_reason == "risk: ATR stop").sum())
    st.bar_chart(pd.Series(act, name="count"))
