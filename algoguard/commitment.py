"""Commitment lock: a trader can tighten a rule at once, but loosening one only takes effect
after a waiting period.

This closes the obvious loophole in any self-imposed risk rule: switching it off right after
a bad day, in the heat of the moment. Rules:

- Tighter or equal to the committed value -> applies immediately (and cancels any pending change).
- Looser -> queued; it applies once its waiting period has passed. Changing the requested value
  again restarts the clock, so the wait cannot be gamed.
- Turning the lock off and shortening the waiting period count as loosening too.
- While the lock is off, every change applies immediately.

The state is a plain dict so it can be saved as JSON (see `load` / `save`).
"""
from __future__ import annotations

import json
import math
import os
from datetime import datetime, timedelta
from pathlib import Path

LOCK_FILE = Path(os.environ.get("ALGOGUARD_LOCK", Path(__file__).resolve().parent.parent / "rules_lock.json"))

# For each field: how "loose" a value is. Higher = looser. None (rule off) is the loosest.
_HIGHER_IS_LOOSER = {"daily_loss_limit", "consec_loss_limit", "max_drawdown", "vix_limit",
                     "stop_atr_mult", "vol_target", "max_position_pct"}
_SHORTER_IS_LOOSER = {"daily_loss_cooldown", "consec_loss_cooldown", "dd_halt_days", "wait_hours"}
_TRUE_IS_TIGHTER = {"dd_flatten", "lock_enabled"}

LABELS = {
    "daily_loss_limit": "Daily loss limit", "daily_loss_cooldown": "Cooldown after a bad day",
    "consec_loss_limit": "Losing-streak limit", "consec_loss_cooldown": "Losing-streak pause",
    "max_drawdown": "Drawdown breaker level", "dd_halt_days": "Breaker halt length",
    "dd_flatten": "Breaker sells everything", "vix_limit": "India VIX filter",
    "stop_atr_mult": "ATR stop-loss", "vol_target": "Volatility sizing",
    "max_position_pct": "Max size of one position", "lock_enabled": "Commitment lock",
    "wait_hours": "Waiting period (hours)",
}


def looseness(field: str, value) -> float:
    if field in _TRUE_IS_TIGHTER:
        return 0.0 if value else 1.0
    if field in _SHORTER_IS_LOOSER:
        return -float(value)
    if field in _HIGHER_IS_LOOSER:
        return math.inf if value is None else float(value)
    return 0.0  # unknown fields are never treated as loosening


def reconcile(state: dict | None, requested: dict, now: datetime) -> tuple[dict, dict]:
    """Return (new state, effective settings). `requested` is what the controls currently show."""
    if not state:
        return {"committed": dict(requested), "pending": {}}, dict(requested)
    committed = {**requested, **state.get("committed", {})}  # fields added later default to the request
    pending = dict(state.get("pending", {}))

    # 1) queued loosenings whose wait is over become the committed value
    for f, p in list(pending.items()):
        if datetime.fromisoformat(p["effective_at"]) <= now:
            committed[f] = p["value"]
            del pending[f]

    locked = bool(committed.get("lock_enabled"))
    wait = timedelta(hours=float(committed.get("wait_hours", 24)))
    for f, new in requested.items():
        old = committed.get(f)
        if not locked or looseness(f, new) <= looseness(f, old):
            committed[f] = new
            pending.pop(f, None)
        elif f not in pending or pending[f]["value"] != new:
            pending[f] = {"value": new, "requested_at": now.isoformat(timespec="seconds"),
                          "effective_at": (now + wait).isoformat(timespec="seconds")}
    return {"committed": committed, "pending": pending}, dict(committed)


def load(path: Path = LOCK_FILE) -> dict | None:
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return None


def save(state: dict, path: Path = LOCK_FILE) -> None:
    Path(path).write_text(json.dumps(state, indent=2))
