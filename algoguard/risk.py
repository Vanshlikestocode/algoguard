"""The guardrail layer (TradeGuardian, rebuilt as the risk engine of an algo).

Design principle: risk rules can only BLOCK new entries or FORCE exits. They never open a
position. Every intervention is written to an audit log with the rule that fired, so the
system can explain itself ("why didn't my algo trade on 14 March?").

All decisions for day t use only information available at the close of day t-1.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace

import pandas as pd


@dataclass
class RiskConfig:
    enabled: bool = True
    # Sizing
    max_position_pct: float = 0.15        # hard cap on any one position, fraction of equity
    vol_target: float | None = 0.25       # scale position size by target_vol / stock_vol; None = equal weight
    # Per-trade protection
    stop_atr_mult: float | None = 3.0     # protective stop at entry - k*ATR; None = off
    # Session / behavioural rules (the old TradeGuardian ideas, now enforceable)
    daily_loss_limit: float | None = 0.02  # portfolio down more than 2% in a day ...
    daily_loss_cooldown: int = 2           # ... no new entries for this many sessions
    consec_loss_limit: int | None = 3      # this many losing trades in a row ...
    consec_loss_cooldown: int = 5          # ... pause new entries for this many sessions
    # Capital protection
    max_drawdown: float | None = 0.15      # drawdown from peak beyond this ...
    dd_halt_days: int = 20                 # ... halt new entries this many sessions, then re-arm
    dd_flatten: bool = True                # True: also sell everything at the next open (v1). False: block entries only
    # Market regime
    vix_limit: float | None = 25.0         # India VIX above this: no new entries

    def as_dict(self):
        return asdict(self)


RAW = RiskConfig(enabled=False, vol_target=None, stop_atr_mult=None, daily_loss_limit=None,
                 consec_loss_limit=None, max_drawdown=None, vix_limit=None, max_position_pct=1.0)
GUARDED = RiskConfig()

# Starting points for different risk appetites. Hand-picked, NOT tuned on the data: they show
# that the same engine can serve a cautious and an aggressive trader. Balanced = v1 defaults.
PROFILES = {
    "Conservative": replace(GUARDED, daily_loss_limit=0.015, daily_loss_cooldown=3, consec_loss_limit=3,
                            consec_loss_cooldown=10, max_drawdown=0.10, dd_halt_days=20, vix_limit=22.0,
                            stop_atr_mult=2.5, vol_target=0.20, max_position_pct=0.10),
    "Balanced": GUARDED,
    "Aggressive": replace(GUARDED, daily_loss_limit=0.04, daily_loss_cooldown=1, consec_loss_limit=5,
                          consec_loss_cooldown=3, max_drawdown=0.25, dd_halt_days=10, dd_flatten=False,
                          vix_limit=None, stop_atr_mult=5.0, vol_target=0.35, max_position_pct=0.25),
}

RULES = ["stop_atr_mult", "daily_loss_limit", "consec_loss_limit", "max_drawdown", "vix_limit", "vol_target"]
RULE_LABELS = {
    "stop_atr_mult": "ATR stop-loss",
    "daily_loss_limit": "Daily loss limit",
    "consec_loss_limit": "Losing-streak cooldown",
    "max_drawdown": "Drawdown circuit breaker",
    "vix_limit": "India VIX filter",
    "vol_target": "Volatility sizing",
}


def only(rule: str) -> RiskConfig:
    """RAW config with exactly one rule switched on (for ablation)."""
    on = {r: getattr(GUARDED, r) for r in [rule]}
    return replace(RAW, enabled=True, **on)


def without(rule: str) -> RiskConfig:
    return replace(GUARDED, **{rule: None})


@dataclass
class RiskManager:
    cfg: RiskConfig
    dates: pd.DatetimeIndex
    cooldown_until: int = -1
    pause_until: int = -1
    halt_until: int = -1
    flatten_at: int = -1
    consec_losses: int = 0
    peak: float | None = None
    events: list = field(default_factory=list)
    blocked: dict = field(default_factory=dict)

    def _log(self, t, rule, action, detail):
        self.events.append({"date": self.dates[t], "rule": rule, "action": action, "detail": detail})

    # ---- decisions taken at the open of day t -------------------------------------
    def entry_block_reason(self, t: int, vix_prev: float | None) -> str | None:
        c = self.cfg
        if not c.enabled:
            return None
        if t <= self.halt_until:
            return "max_drawdown"
        if t <= self.cooldown_until:
            return "daily_loss_limit"
        if t <= self.pause_until:
            return "consec_loss_limit"
        if c.vix_limit is not None and vix_prev is not None and vix_prev == vix_prev and vix_prev > c.vix_limit:
            return "vix_limit"
        return None

    def must_flatten(self, t: int) -> bool:
        return self.cfg.enabled and t == self.flatten_at

    def record_block(self, t: int, rule: str, symbol: str):
        self.blocked[rule] = self.blocked.get(rule, 0) + 1
        self._log(t, rule, "BLOCKED ENTRY", symbol)

    # ---- state update at the close of day t ---------------------------------------
    def on_close(self, t: int, equity: float, daily_ret: float, closed_pnls: list[float]):
        c = self.cfg
        if not c.enabled:
            return
        if self.peak is None:
            self.peak = equity
        # daily loss limit
        if c.daily_loss_limit is not None and daily_ret <= -c.daily_loss_limit:
            self.cooldown_until = max(self.cooldown_until, t + c.daily_loss_cooldown)
            self._log(t, "daily_loss_limit", "COOLDOWN",
                      f"day P&L {daily_ret:.2%} breached -{c.daily_loss_limit:.0%}; no entries for {c.daily_loss_cooldown} sessions")
        # losing streak
        if c.consec_loss_limit is not None:
            for p in closed_pnls:
                self.consec_losses = self.consec_losses + 1 if p < 0 else 0
                if self.consec_losses >= c.consec_loss_limit:
                    self.pause_until = max(self.pause_until, t + c.consec_loss_cooldown)
                    self._log(t, "consec_loss_limit", "PAUSE",
                              f"{self.consec_losses} losing trades in a row; pause {c.consec_loss_cooldown} sessions")
                    self.consec_losses = 0
        # drawdown circuit breaker
        if t > self.halt_until:
            self.peak = max(self.peak, equity)
        if c.max_drawdown is not None and t > self.halt_until:
            dd = equity / self.peak - 1
            if dd <= -c.max_drawdown:
                self.halt_until = t + c.dd_halt_days
                if c.dd_flatten:
                    self.flatten_at = t + 1
                    self._log(t, "max_drawdown", "HALT + FLATTEN",
                              f"drawdown {dd:.1%} breached -{c.max_drawdown:.0%}; all positions closed, halted {c.dd_halt_days} sessions")
                else:
                    self._log(t, "max_drawdown", "HALT",
                              f"drawdown {dd:.1%} breached -{c.max_drawdown:.0%}; positions kept, no new entries for {c.dd_halt_days} sessions")
        if c.max_drawdown is not None and t == self.halt_until:
            self.peak = equity  # re-arm from the post-halt level
            self._log(t, "max_drawdown", "RE-ARMED", "halt period over, trading resumes")
