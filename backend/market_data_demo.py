"""
FinAlly Market Data Demo
========================
Rich terminal dashboard showing the GBM simulator live.

Run:  python3 market_data_demo.py
      python3 market_data_demo.py --duration 120   # run for 2 minutes
      python3 market_data_demo.py --tickers AAPL TSLA NVDA

Press Ctrl+C to exit early.
"""

import argparse
import asyncio
import sys
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime

sys.path.insert(0, ".")

from rich.align import Align
from rich.columns import Columns
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from app.market.cache import PriceCache
from app.market.models import PriceUpdate
from app.market.simulator import SimulatorDataSource

SPARKLINE_WIDTH = 20
MAX_EVENTS = 18
DEFAULT_DURATION = 60
DEFAULT_TICKERS = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX"]

# Spark character blocks, low→high
SPARK_CHARS = "▁▂▃▄▅▆▇█"


@dataclass
class TickerState:
    ticker: str
    price: float = 0.0
    prev_price: float = 0.0
    history: deque = field(default_factory=lambda: deque(maxlen=SPARKLINE_WIDTH))
    ticks: int = 0

    @property
    def change(self) -> float:
        return self.price - self.prev_price if self.prev_price else 0.0

    @property
    def change_pct(self) -> float:
        return (self.change / self.prev_price * 100) if self.prev_price else 0.0

    def update(self, u: PriceUpdate) -> None:
        self.prev_price = self.price if self.price else u.prev_price
        self.price = u.price
        self.history.append(u.price)
        self.ticks += 1


def make_sparkline(history: deque, width: int = SPARKLINE_WIDTH) -> Text:
    """Render a mini sparkline from a price history deque."""
    prices = list(history)
    if len(prices) < 2:
        return Text("·" * width, style="dim")

    lo, hi = min(prices), max(prices)
    span = hi - lo or 1.0

    chars = []
    for p in prices[-width:]:
        idx = int((p - lo) / span * (len(SPARK_CHARS) - 1))
        chars.append(SPARK_CHARS[idx])

    # Pad left if shorter than width
    line = "·" * (width - len(chars)) + "".join(chars)

    # Color the sparkline by trend (last vs first visible price)
    if prices[-1] >= prices[0]:
        style = "green"
    else:
        style = "red"

    return Text(line, style=style)


def make_arrow(change: float) -> Text:
    if change > 0:
        return Text(" ▲", style="bold green")
    elif change < 0:
        return Text(" ▼", style="bold red")
    else:
        return Text(" ─", style="dim")


def make_price_table(states: dict[str, TickerState]) -> Table:
    table = Table(
        show_header=True,
        header_style="bold #ecad0a",
        border_style="#303050",
        box=None,
        padding=(0, 1),
        expand=True,
    )

    table.add_column("TICKER", style="bold #209dd7", width=8)
    table.add_column("PRICE", justify="right", width=10)
    table.add_column("CHG", justify="right", width=8)
    table.add_column("CHG %", justify="right", width=8)
    table.add_column("SPARKLINE", width=SPARKLINE_WIDTH + 2)
    table.add_column("TICKS", justify="right", style="dim", width=6)

    for ticker in sorted(states):
        s = states[ticker]
        if s.price == 0:
            table.add_row(ticker, "–", "–", "–", Text("·" * SPARKLINE_WIDTH, style="dim"), "0")
            continue

        chg = s.change
        pct = s.change_pct
        arrow = make_arrow(chg)

        price_style = "bold green" if chg > 0 else "bold red" if chg < 0 else "white"
        price_text = Text(f"${s.price:>8.2f}", style=price_style)

        chg_text = Text(f"{chg:+.2f}", style="green" if chg >= 0 else "red")
        pct_text = Text(f"{pct:+.2f}%", style="green" if pct >= 0 else "red")

        ticker_cell = Text(ticker)
        ticker_cell.append_text(arrow)

        table.add_row(
            ticker_cell,
            price_text,
            chg_text,
            pct_text,
            make_sparkline(s.history),
            str(s.ticks),
        )

    return table


def make_event_log(events: deque) -> Table:
    table = Table(
        show_header=True,
        header_style="bold #ecad0a",
        border_style="#303050",
        box=None,
        padding=(0, 1),
        expand=True,
    )
    table.add_column("TIME", style="dim", width=10)
    table.add_column("TICKER", style="bold #209dd7", width=8)
    table.add_column("EVENT", width=40)

    for ts, ticker, msg, style in list(events):
        table.add_row(ts, ticker, Text(msg, style=style))

    return table


def make_header(elapsed: float, duration: int, tick_count: int) -> Panel:
    remaining = max(0, duration - int(elapsed))
    bar_width = 30
    filled = int((elapsed / duration) * bar_width) if duration else 0
    bar = "█" * filled + "░" * (bar_width - filled)

    left = Text()
    left.append("FinAlly", style="bold #ecad0a")
    left.append(" Market Data Demo", style="white")

    right = Text()
    right.append(f"[{bar}] ", style="#209dd7")
    right.append(f"{remaining}s remaining", style="dim")
    right.append(f"  ticks: {tick_count}", style="dim")

    row = Columns([left, Align(right, align="right")], expand=True)
    return Panel(row, style="#303050", padding=(0, 1))


def make_layout() -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body"),
        Layout(name="footer", size=3),
    )
    layout["body"].split_row(
        Layout(name="prices", ratio=3),
        Layout(name="events", ratio=2),
    )
    return layout


async def run_demo(tickers: list[str], duration: int) -> None:
    console = Console()

    cache = PriceCache()
    source = SimulatorDataSource()
    await source.start(tickers)

    states: dict[str, TickerState] = {t: TickerState(t) for t in tickers}
    events: deque = deque(maxlen=MAX_EVENTS)
    total_ticks = 0
    last_version = -1
    start_time = asyncio.get_event_loop().time()

    layout = make_layout()

    def refresh():
        elapsed = asyncio.get_event_loop().time() - start_time
        layout["header"].update(make_header(elapsed, duration, total_ticks))
        layout["prices"].update(
            Panel(
                make_price_table(states),
                title="[bold #ecad0a]Live Prices[/]",
                border_style="#303050",
            )
        )
        layout["events"].update(
            Panel(
                make_event_log(events),
                title="[bold #ecad0a]Event Log[/]",
                border_style="#303050",
            )
        )
        layout["footer"].update(
            Panel(
                Text("Ctrl+C to exit early  •  GBM simulator with correlated market factor  •  β-weighted sector moves", style="dim"),
                border_style="#303050",
                padding=(0, 1),
            )
        )

    try:
        with Live(layout, console=console, refresh_per_second=4, screen=True):
            deadline = start_time + duration
            while asyncio.get_event_loop().time() < deadline:
                await asyncio.sleep(0.12)

                current_version = cache.version
                if current_version == last_version:
                    continue
                last_version = current_version

                all_prices = cache.get_all()
                for ticker, update in all_prices.items():
                    if ticker not in states:
                        states[ticker] = TickerState(ticker)
                    old_price = states[ticker].price
                    states[ticker].update(update)
                    total_ticks += 1

                    # Log notable moves (>= 1% in a single tick)
                    if old_price > 0:
                        pct = (update.price - old_price) / old_price * 100
                        if abs(pct) >= 1.0:
                            ts = datetime.now().strftime("%H:%M:%S")
                            direction = "spike" if pct > 0 else "drop"
                            msg = f"{direction} {pct:+.2f}%  ${update.price:.2f}"
                            style = "bold green" if pct > 0 else "bold red"
                            events.appendleft((ts, ticker, msg, style))

                refresh()

    except KeyboardInterrupt:
        pass
    finally:
        await source.stop()
        console.print("\n[dim]Simulator stopped.[/dim]")


def main() -> None:
    parser = argparse.ArgumentParser(description="FinAlly market data terminal demo")
    parser.add_argument("--duration", type=int, default=DEFAULT_DURATION, help="Run duration in seconds (default: 60)")
    parser.add_argument("--tickers", nargs="+", default=DEFAULT_TICKERS, help="Tickers to track")
    args = parser.parse_args()

    tickers = [t.upper() for t in args.tickers]
    asyncio.run(run_demo(tickers, args.duration))


if __name__ == "__main__":
    main()
