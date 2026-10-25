"""Shared validation helpers for EUR/JPY 15-minute candle data."""

from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite
from typing import Any, Iterable

CSV_FIELDS = ["timestamp", "symbol", "open", "high", "low", "close", "volume"]
REQUIRED_FIELDS = ["timestamp", "symbol", "open", "high", "low", "close"]


@dataclass
class ValidationResult:
    errors: list[str]
    duplicate_timestamps: int = 0
    invalid_ohlc: int = 0
    non_interval_gaps: list[tuple[datetime, datetime]] | None = None

    @property
    def is_valid(self) -> bool:
        return not self.errors


def parse_timestamp(value: str) -> datetime:
    """Parse an LSE ISO timestamp and normalize it to UTC."""
    timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(timezone.utc)


def validate_candles(candles: Iterable[dict[str, Any]], timeframe_minutes: int | None = None) -> ValidationResult:
    """Validate candle fields, OHLC relationships, ordering, and timestamps."""
    errors: list[str] = []
    timestamps: list[datetime] = []
    invalid_ohlc = 0
    for row_number, candle in enumerate(candles, start=1):
        missing = [field for field in REQUIRED_FIELDS if field not in candle or candle[field] in (None, "")]
        if missing:
            errors.append(f"Row {row_number} is missing: {', '.join(missing)}")
            continue
        try:
            timestamp = parse_timestamp(str(candle["timestamp"]))
            open_price, high, low, close = (float(candle[field]) for field in ("open", "high", "low", "close"))
        except (TypeError, ValueError) as error:
            errors.append(f"Row {row_number} has an invalid timestamp or price: {error}")
            continue
        timestamps.append(timestamp)
        if not all(isfinite(price) for price in (open_price, high, low, close)):
            errors.append(f"Row {row_number} has a non-finite OHLC price.")
        elif high < max(open_price, close) or low > min(open_price, close) or high < low:
            invalid_ohlc += 1

    duplicate_timestamps = len(timestamps) - len(set(timestamps))
    if duplicate_timestamps:
        errors.append(f"Found {duplicate_timestamps} duplicate timestamp(s).")
    if invalid_ohlc:
        errors.append(f"Found {invalid_ohlc} invalid OHLC candle(s).")
    if timestamps != sorted(timestamps):
        errors.append("Candles are not in chronological order.")

    gaps: list[tuple[datetime, datetime]] = []
    if timeframe_minutes is not None and timestamps == sorted(timestamps):
        interval_seconds = timeframe_minutes * 60
        for previous, current in zip(timestamps, timestamps[1:]):
            if (current - previous).total_seconds() != interval_seconds:
                gaps.append((previous, current))
    return ValidationResult(errors, duplicate_timestamps, invalid_ohlc, gaps)
