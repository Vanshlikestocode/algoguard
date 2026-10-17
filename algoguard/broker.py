"""Execution layer designed around SEBI's retail algo framework (fully applicable from
1 April 2026): static-IP whitelisting, daily 2FA login, max 10 orders/second, and market
orders converted to Market Price Protection (MPP) orders.

The engine talks to a Broker interface. SimBroker is used for paper trading; KiteBroker
shows how the same interface maps to Zerodha Kite Connect (requires a registered app,
a whitelisted static IP and a daily access token, so it is not exercised in tests).
"""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field


class OrderRateLimiter:
    """Sliding-window limiter: never exceed `max_per_sec` orders in any 1-second window."""

    def __init__(self, max_per_sec: int = 10, clock=time.monotonic, sleep=time.sleep):
        self.max, self.clock, self.sleep = max_per_sec, clock, sleep
        self.sent = deque()

    def acquire(self):
        while True:
            now = self.clock()
            while self.sent and now - self.sent[0] >= 1.0:
                self.sent.popleft()
            if len(self.sent) < self.max:
                self.sent.append(now)
                return
            self.sleep(1.0 - (now - self.sent[0]) + 1e-3)


def mpp_limit_price(side: str, ltp: float, protection_pct: float = 0.01, tick: float = 0.05) -> float:
    """Convert a 'market' order into a protected limit order: buy no higher than LTP*(1+p),
    sell no lower than LTP*(1-p), rounded to the exchange tick size."""
    raw = ltp * (1 + protection_pct) if side == "BUY" else ltp * (1 - protection_pct)
    ticks = (raw / tick)
    ticks = int(ticks) if side == "BUY" else int(ticks + 0.999999)
    return round(ticks * tick, 2)


@dataclass
class Order:
    symbol: str
    side: str          # BUY / SELL
    qty: int
    limit: float
    tag: str = ""      # strategy ID tag (exchanges require algo orders to be tagged)


@dataclass
class SimBroker:
    """Paper broker: fills a protected limit order if the next price is within the limit."""
    cash: float = 1_000_000
    positions: dict = field(default_factory=dict)
    log: list = field(default_factory=list)
    limiter: OrderRateLimiter = field(default_factory=OrderRateLimiter)
    session_date: str | None = None   # simulates the once-a-day 2FA login requirement

    def login(self, date: str):
        self.session_date = date

    def place(self, order: Order, fill_price: float, date: str) -> bool:
        if self.session_date != date:
            raise PermissionError("No valid session for today: daily 2FA login required")
        self.limiter.acquire()
        ok = fill_price <= order.limit if order.side == "BUY" else fill_price >= order.limit
        if ok:
            sign = 1 if order.side == "BUY" else -1
            self.positions[order.symbol] = self.positions.get(order.symbol, 0) + sign * order.qty
            self.cash -= sign * order.qty * fill_price
        self.log.append({"date": date, **order.__dict__, "fill": fill_price if ok else None,
                         "status": "FILLED" if ok else "REJECTED (outside MPP limit)"})
        return ok


class KiteBroker:  # pragma: no cover - needs live credentials
    """Mapping of the Broker interface onto Kite Connect. Illustrative; see README."""

    def __init__(self, api_key: str, access_token: str):
        from kiteconnect import KiteConnect
        self.kite = KiteConnect(api_key=api_key)
        self.kite.set_access_token(access_token)  # obtained via the daily login flow
        self.limiter = OrderRateLimiter()

    def place(self, order: Order):
        self.limiter.acquire()
        return self.kite.place_order(
            variety=self.kite.VARIETY_REGULAR, exchange=self.kite.EXCHANGE_NSE,
            tradingsymbol=order.symbol.replace(".NS", ""), transaction_type=order.side,
            quantity=order.qty, product=self.kite.PRODUCT_CNC,
            order_type=self.kite.ORDER_TYPE_LIMIT, price=order.limit, tag=order.tag[:20])
