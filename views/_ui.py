"""Small shared helpers for the VolSelect site pages (not a page itself)."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RESULTS, VS = ROOT / "results", ROOT / "results" / "vs"
ACTION_COLOR = {"BUY": "#2e7d4f", "SELL": "#b4483c", "BLOCKED": "#9a6b00", "WAIT": "#5b6675", "HOLD": "#1F6F8B"}
MAIN, STRESS = "Regime switch (LR), no trigger", "Stress model only"
EW, NIFTY = "Equal-weight NIFTY 50 (benchmark)", "NIFTY 50 buy and hold (benchmark)"


def read_json(path: Path) -> dict | None:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def regime_label(regime: str | None) -> str:
    """Plain label with a coloured dot, for st.metric (which cannot colour its value)."""
    return "–" if not regime else {"calm": "🟢 ", "rising": "🟠 ", "high": "🔴 "}.get(regime, "") + regime.capitalize()


def table(name: str) -> pd.DataFrame:
    return pd.read_csv(VS / f"table_{name}.csv", index_col=0)


def pct(x, d=1, sign=False) -> str:
    return "–" if pd.isna(x) else (f"{x:+.{d}f}%" if sign else f"{x:.{d}f}%").replace("-", "−")
