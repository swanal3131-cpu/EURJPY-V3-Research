"""UTC time buckets, never groups of the last N available rows."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

from config.backtest_config import StructureConfig
from data.data_loader import Candle


@dataclass(frozen=True)
class StructureBar:
    open_time: datetime
    close_time: datetime
    open: float
    high: float
    low: float
    close: float
    source_count: int
    complete: bool
    information_available_at: datetime


def bucket_open(timestamp: datetime, config: StructureConfig) -> datetime:
    if timestamp.tzinfo is None:
        raise ValueError("Source timestamps must have a timezone.")
    origin = datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=config.anchor_minutes_utc)
    duration = timedelta(minutes=config.structure_minutes)
    return origin + ((timestamp.astimezone(timezone.utc) - origin) // duration) * duration


def aggregate_candles(
    candles: Iterable[Candle], config: StructureConfig = StructureConfig(),
    as_of: datetime | None = None,
) -> list[StructureBar]:
    """Return nonempty buckets, tagged with when their final OHLC is available.

    With as_of, consume only source candles closed by that time and return only
    closed structure buckets. Without as_of, produce an offline annotated table;
    callers must respect information_available_at. Entirely empty intervals are
    omitted, not filled. Completeness checks the exact expected timestamp set.
    """
    if as_of is not None and as_of.tzinfo is None:
        raise ValueError("as_of must have a timezone.")
    groups: dict[datetime, list[Candle]] = {}
    previous = None
    step = timedelta(minutes=config.source_minutes)
    for candle in candles:
        if candle.timestamp.tzinfo is None:
            raise ValueError("Source timestamps must have a timezone.")
        timestamp = candle.timestamp.astimezone(timezone.utc)
        if previous is not None and timestamp <= previous:
            raise ValueError("Source candles must be ordered and unique.")
        previous = timestamp
        start = bucket_open(timestamp, config)
        if (timestamp - start) % step != timedelta(0):
            raise ValueError("Source timestamp is off the configured candle grid.")
        if as_of is not None and timestamp + step > as_of:
            continue
        groups.setdefault(start, []).append(candle)

    bars = []
    for start, rows in groups.items():
        end = start + timedelta(minutes=config.structure_minutes)
        if as_of is not None and end > as_of:
            continue
        expected = {start + n * step for n in range(config.expected_source_count)}
        complete = {row.timestamp for row in rows} == expected
        bars.append(StructureBar(
            start, end, rows[0].open, max(row.high for row in rows),
            min(row.low for row in rows), rows[-1].close, len(rows), complete, end,
        ))
    return bars
