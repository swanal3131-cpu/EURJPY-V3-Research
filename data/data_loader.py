"""Load validated EUR/JPY 15-minute candles for research and backtests."""

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

try:  # Supports both `python data/...py` and `from data...` imports.
    from .validation import parse_timestamp, validate_candles
except ImportError:
    from validation import parse_timestamp, validate_candles


DEFAULT_DATA_FILE = Path("data/raw/eurjpy_15m_2015_2020.csv")
EXPECTED_SYMBOL = "EUR/JPY"


@dataclass(frozen=True)
class Candle:
    """One immutable OHLCV candle with numeric prices and a UTC timestamp."""

    timestamp: datetime
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: float


def load_eurjpy_15m(
    filename: Path | str = DEFAULT_DATA_FILE,
    start: str | None = None,
    end: str | None = None,
) -> list[Candle]:
    """Load valid EUR/JPY candles, optionally restricted to ``[start, end)``.

    ``start`` is inclusive and ``end`` is exclusive. They may be ISO dates or
    timestamps. The complete source file is validated before filtering so a
    backtest never unknowingly starts with malformed or duplicated raw data.
    """
    path = Path(filename)
    if not path.exists():
        raise FileNotFoundError(f"Candle file was not found: {path}")

    with path.open("r", newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))

    result = validate_candles(rows, timeframe_minutes=15)
    if not result.is_valid:
        raise ValueError("Candle file failed validation:\n- " + "\n- ".join(result.errors))

    wrong_symbols = [row["symbol"] for row in rows if row["symbol"] != EXPECTED_SYMBOL]
    if wrong_symbols:
        raise ValueError(f"Expected only {EXPECTED_SYMBOL} candles, but found another symbol.")

    start_timestamp = parse_timestamp(start) if start else None
    end_timestamp = parse_timestamp(end) if end else None
    if start_timestamp and end_timestamp and start_timestamp >= end_timestamp:
        raise ValueError("start must be earlier than end.")

    candles = [
        Candle(
            timestamp=parse_timestamp(row["timestamp"]),
            symbol=row["symbol"],
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=float(row.get("volume") or 0.0),
        )
        for row in rows
    ]
    return [
        candle
        for candle in candles
        if (start_timestamp is None or candle.timestamp >= start_timestamp)
        and (end_timestamp is None or candle.timestamp < end_timestamp)
    ]
