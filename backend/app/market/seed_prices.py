SEED_PRICES: dict[str, float] = {
    "AAPL": 190.0,
    "GOOGL": 175.0,
    "MSFT": 415.0,
    "AMZN": 185.0,
    "TSLA": 250.0,
    "NVDA": 875.0,
    "META": 500.0,
    "JPM": 200.0,
    "V": 285.0,
    "NFLX": 650.0,
}

TICKER_PARAMS: dict[str, dict] = {
    "AAPL":  {"drift": 0.08, "vol": 0.22, "beta": 0.70},
    "GOOGL": {"drift": 0.07, "vol": 0.24, "beta": 0.70},
    "MSFT":  {"drift": 0.09, "vol": 0.20, "beta": 0.70},
    "AMZN":  {"drift": 0.08, "vol": 0.28, "beta": 0.70},
    "TSLA":  {"drift": 0.05, "vol": 0.55, "beta": 0.70},
    "NVDA":  {"drift": 0.12, "vol": 0.45, "beta": 0.70},
    "META":  {"drift": 0.08, "vol": 0.30, "beta": 0.70},
    "JPM":   {"drift": 0.06, "vol": 0.18, "beta": 0.30},
    "V":     {"drift": 0.07, "vol": 0.17, "beta": 0.30},
    "NFLX":  {"drift": 0.06, "vol": 0.35, "beta": 0.70},
}

DEFAULT_PARAMS: dict = {"drift": 0.07, "vol": 0.25, "beta": 0.50}

TECH_TICKERS: frozenset[str] = frozenset(
    {"AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "NFLX"}
)
FINANCE_TICKERS: frozenset[str] = frozenset({"JPM", "V"})
