"""Daily live update: fetch the latest NSE prices, extend the forward paper-trading record and write
today's plan for the next open. Run after the market closes; GitHub Actions does it every weekday at
18:00 IST (.github/workflows/live-update.yml) and commits the result, so each day is timestamped.

    python live_update.py               # download fresh prices, then update live/
    python live_update.py --no-download # reuse the prices already in live/data/

Writes to live/ only. The research data (data/) and results (results/) are never touched.
Paper trading only: no orders are sent anywhere.
"""
from __future__ import annotations

import argparse
from datetime import datetime

import pandas as pd

from algoguard import data, live, universe
from algoguard.strategies import STRATEGIES, build_signals


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-download", action="store_true")
    a = ap.parse_args()
    ag_dir, vs_dir = live.LIVE_DATA / "algoguard", live.LIVE_DATA / "nifty50"
    if not a.no_download:
        print("Downloading latest prices ...")
        # 2 years covers every indicator's warm-up (200-day average, 100-day EMA, 55-day channel)
        data.download(start=(live.START - pd.Timedelta(days=730)).date().isoformat(), force=True, folder=ag_dir)
        universe.download(start="2012-01-01", force=True, folder=vs_dir)  # VolSelect trains on the full history

    now = datetime.now(live.IST)
    prices, vix, index = live.drop_unfinished(*data.load_real(folder=ag_dir), now=now)
    last = next(iter(prices.values())).index[-1]
    rows, plans = [], []
    for name, (strategy, cfg) in live.PORTFOLIOS.items():
        sig, res = live.forward(prices, vix, strategy, cfg)
        rows.append(live.day_rows(name, sig, res, vix, index))
        plans += live.plan_next_open(name, sig, res, vix)
    new = pd.concat(rows, ignore_index=True)
    added, drift = live.append_ledger(new) if len(new) else (0, 0.0)
    signals = {live.SHORT[s]: [t.replace(".NS", "") for t, v in build_signals(prices, fn).iloc[-1].items() if v == 1]
               for s, fn in STRATEGIES.items()}  # what each strategy says at the last close, record or not
    live.write_json({"after_close_of": last.date().isoformat(), "orders": plans, "long_signals": signals},
                    live.LIVE / "plan.json")

    rank, state = live.volselect_snapshot(vs_dir, now=now)
    rank.round(4).to_csv(live.LIVE / "vs_ranking.csv", index=False)
    live.write_json(state, live.LIVE / "vs_state.json")
    live.write_json({"updated_at_ist": now.strftime("%Y-%m-%d %H:%M"), "last_completed_session": last.date().isoformat(),
                     "record_starts": live.START.date().isoformat(), "rows_added": added,
                     "largest_restatement_rs": round(drift, 2)}, live.LIVE / "status.json")
    print(f"Last completed session {last.date()}. Ledger rows added: {added}. "
          f"Orders planned for the next open: {sum(o['action'] in ('BUY', 'SELL') for o in plans)}. "
          f"VolSelect regime: {state['regime']} (p_high {state['p_high']:.2f}).")
    if drift > 1:
        print(f"Note: Yahoo revised past prices; recomputed values differ from the stored record by up to Rs {drift:,.0f}. "
              "Stored rows are kept as recorded.")


if __name__ == "__main__":
    main()
