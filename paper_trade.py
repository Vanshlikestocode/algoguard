"""Paper-trading replay: walks the last N sessions one day at a time through the SAME
strategy + risk engine, but routes orders through the broker layer (daily login, 10 orders/s
limit, MPP-protected limit orders, strategy tags). This is the bridge from backtest to live.

    python paper_trade.py --days 60          # real data
    python paper_trade.py --days 60 --demo
"""
from __future__ import annotations

import argparse
import math

import pandas as pd

from algoguard import data
from algoguard.broker import Order, SimBroker, mpp_limit_price
from algoguard.risk import GUARDED, RiskManager
from algoguard.strategies import STRATEGIES, build_signals


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=60)
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--strategy", default=list(STRATEGIES)[0], choices=list(STRATEGIES))
    a = ap.parse_args()

    prices, vix, _ = data.make_synthetic() if a.demo else data.load_real()
    sig = build_signals(prices, STRATEGIES[a.strategy])
    dates = sig.index
    start = len(dates) - a.days
    broker = SimBroker()
    risk = RiskManager(GUARDED, dates)
    syms = list(prices)
    tag = "AG-" + a.strategy.split()[0][:6].upper()
    prev_eq = broker.cash

    for t in range(start, len(dates)):
        d = str(dates[t].date())
        broker.login(d)  # daily 2FA session
        block = risk.entry_block_reason(t, vix.iloc[t - 1] if vix is not None else None)
        flatten = risk.must_flatten(t)
        eq = broker.cash + sum(q * prices[s]["close"].iloc[t - 1] for s, q in broker.positions.items())
        for s in syms:
            px_prev, px_open = prices[s]["close"].iloc[t - 1], prices[s]["open"].iloc[t]
            held = broker.positions.get(s, 0)
            want = sig[s].iloc[t - 1] == 1 and not flatten
            if held > 0 and not want:
                broker.place(Order(s, "SELL", held, mpp_limit_price("SELL", px_prev), tag), px_open, d)
            elif held == 0 and want:
                if block:
                    risk.record_block(t, block, s)
                    continue
                q = math.floor(min(GUARDED.max_position_pct, 1 / len(syms)) * eq / px_prev)
                if q > 0:
                    broker.place(Order(s, "BUY", q, mpp_limit_price("BUY", px_prev), tag), px_open, d)
        eq_close = broker.cash + sum(q * prices[s]["close"].iloc[t] for s, q in broker.positions.items())
        risk.on_close(t, eq_close, eq_close / prev_eq - 1, [])
        prev_eq = eq_close

    log = pd.DataFrame(broker.log)
    print(f"Paper run: {a.days} sessions, {len(log)} orders "
          f"({(log.status == 'FILLED').sum() if len(log) else 0} filled, "
          f"{(log.status != 'FILLED').sum() if len(log) else 0} rejected by MPP protection)")
    print(f"Final equity: Rs {eq_close:,.0f}   Risk interventions: {len(risk.events)}")
    if len(log):
        log.to_csv("paper_orders.csv", index=False)
        print("Order log written to paper_orders.csv")
        print(log.tail(10).to_string(index=False))


if __name__ == "__main__":
    main()
