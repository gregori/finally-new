import time
from dataclasses import dataclass


@dataclass(frozen=True)
class PriceUpdate:
    ticker: str
    price: float
    prev_price: float
    timestamp: float
    change: float
    change_pct: float

    @classmethod
    def from_prices(cls, ticker: str, price: float, prev_price: float) -> "PriceUpdate":
        change = price - prev_price
        change_pct = (change / prev_price * 100) if prev_price else 0.0
        return cls(
            ticker=ticker,
            price=price,
            prev_price=prev_price,
            timestamp=time.time(),
            change=change,
            change_pct=change_pct,
        )
