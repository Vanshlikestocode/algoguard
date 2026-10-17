from datetime import datetime, timedelta

from algoguard.commitment import reconcile
from algoguard.risk import PROFILES, RiskConfig

T0 = datetime(2026, 10, 17, 10, 0)
BASE = {"daily_loss_limit": 0.02, "vix_limit": 25.0, "dd_halt_days": 20, "dd_flatten": True,
        "lock_enabled": True, "wait_hours": 24.0}


def test_first_run_commits_request():
    state, eff = reconcile(None, BASE, T0)
    assert eff == BASE and state["pending"] == {}


def test_tightening_applies_at_once():
    state, _ = reconcile(None, BASE, T0)
    state, eff = reconcile(state, {**BASE, "daily_loss_limit": 0.01, "dd_halt_days": 30}, T0)
    assert eff["daily_loss_limit"] == 0.01 and eff["dd_halt_days"] == 30 and not state["pending"]


def test_loosening_waits_then_applies():
    state, _ = reconcile(None, BASE, T0)
    req = {**BASE, "daily_loss_limit": 0.05, "vix_limit": None}
    state, eff = reconcile(state, req, T0 + timedelta(hours=1))
    assert eff["daily_loss_limit"] == 0.02 and eff["vix_limit"] == 25.0
    assert set(state["pending"]) == {"daily_loss_limit", "vix_limit"}
    state, eff = reconcile(state, req, T0 + timedelta(hours=24, minutes=59))
    assert eff["daily_loss_limit"] == 0.02  # still waiting
    state, eff = reconcile(state, req, T0 + timedelta(hours=25, minutes=1))
    assert eff["daily_loss_limit"] == 0.05 and eff["vix_limit"] is None and not state["pending"]


def test_changing_the_request_restarts_the_clock():
    state, _ = reconcile(None, BASE, T0)
    state, _ = reconcile(state, {**BASE, "daily_loss_limit": 0.03}, T0)
    state, _ = reconcile(state, {**BASE, "daily_loss_limit": 0.04}, T0 + timedelta(hours=20))
    state, eff = reconcile(state, {**BASE, "daily_loss_limit": 0.04}, T0 + timedelta(hours=25))
    assert eff["daily_loss_limit"] == 0.02  # 24h counts from the second change


def test_reverting_cancels_pending():
    state, _ = reconcile(None, BASE, T0)
    state, _ = reconcile(state, {**BASE, "daily_loss_limit": 0.05}, T0)
    state, eff = reconcile(state, BASE, T0 + timedelta(minutes=5))
    assert not state["pending"] and eff["daily_loss_limit"] == 0.02


def test_cannot_escape_by_switching_lock_off_or_shortening_wait():
    state, _ = reconcile(None, BASE, T0)
    state, eff = reconcile(state, {**BASE, "lock_enabled": False, "wait_hours": 0.0, "daily_loss_limit": 0.05}, T0)
    assert eff["lock_enabled"] is True and eff["wait_hours"] == 24.0 and eff["daily_loss_limit"] == 0.02


def test_unlocked_changes_apply_at_once():
    state, _ = reconcile(None, {**BASE, "lock_enabled": False}, T0)
    state, eff = reconcile(state, {**BASE, "lock_enabled": False, "vix_limit": None}, T0)
    assert eff["vix_limit"] is None and not state["pending"]


def test_profiles_are_ordered_by_risk():
    c, b, a = PROFILES["Conservative"], PROFILES["Balanced"], PROFILES["Aggressive"]
    assert isinstance(c, RiskConfig)
    assert c.daily_loss_limit < b.daily_loss_limit < a.daily_loss_limit
    assert c.max_drawdown < b.max_drawdown < a.max_drawdown
    assert c.max_position_pct < b.max_position_pct < a.max_position_pct
