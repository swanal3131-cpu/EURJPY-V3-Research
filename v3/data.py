"""Reuse the project's loader and exact UTC aggregation without old trading rules."""
from dataclasses import asdict
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

from data.data_loader import load_eurjpy_15m
from data.aggregation import aggregate_candles


def prepare_data(path: Path):
    """Return annotated nonempty windows, a quality audit, gaps and raw source data.

    Incomplete windows remain observable execution/valuation events, never SMA
    observations. An execution open is eligible only when a real source candle
    starts exactly at the UTC bucket boundary. Future completeness is irrelevant.
    """
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    candles = load_eurjpy_15m(path)
    if not candles:
        raise ValueError("The source dataset is empty.")
    raw = pd.DataFrame([asdict(c) for c in candles])
    raw['timestamp'] = pd.to_datetime(raw.timestamp, utc=True)
    prices = raw[['open', 'high', 'low', 'close']].to_numpy(float)
    if not np.isfinite(prices).all() or (prices <= 0).any():
        raise ValueError("Prices must be finite and positive.")
    bars = pd.DataFrame([asdict(b) for b in aggregate_candles(candles)])
    groups = raw.groupby(raw.timestamp.dt.floor('4h'))
    bars['first_source_open'] = groups.timestamp.first().to_numpy()
    bars['last_source_close'] = (groups.timestamp.last() + pd.Timedelta(minutes=15)).to_numpy()
    bars['open_available'] = bars.first_source_open.eq(bars.open_time)
    bars['source_hours'] = bars.source_count / 4
    diffs = raw.timestamp.diff()
    gaps = pd.DataFrame({
        'previous_source_open': raw.timestamp.shift(),
        'next_source_open': raw.timestamp,
        'elapsed_hours': diffs.dt.total_seconds() / 3600,
    }).loc[diffs.gt(pd.Timedelta(minutes=15))].copy()
    gaps['missing_15m_intervals'] = (gaps.elapsed_hours * 4 - 1).astype(int)
    # A gap cannot be assigned to a holiday vs. vendor omission from prices alone.
    gaps['classification'] = 'unverified closure or missing observations; never filled'
    expected_buckets = len(pd.date_range(bars.open_time.iloc[0], bars.open_time.iloc[-1], freq='4h'))
    audit = {
        'source_file': path.name, 'source_sha256': digest,
        'raw_rows': len(raw), 'first_source_open': str(raw.timestamp.iloc[0]),
        'last_source_open': str(raw.timestamp.iloc[-1]),
        'last_observation_close': str(raw.timestamp.iloc[-1] + pd.Timedelta(minutes=15)),
        'timestamp_convention': 'UTC candle opens, established by existing README and docs/v2a_v2b.md; not independently vendor-certified',
        'duplicate_timestamps': 0, 'invalid_ohlc': 0,
        'nonempty_4h_windows': len(bars), 'complete_4h_candles': int(bars.complete.sum()),
        'incomplete_4h_windows_excluded_from_sma': int((~bars.complete).sum()),
        'source_rows_in_incomplete_windows': int(bars.loc[~bars.complete, 'source_count'].sum()),
        'empty_4h_windows': expected_buckets - len(bars),
        'source_gaps_over_15m': len(gaps),
        'first_complete_4h_open': str(bars.loc[bars.complete, 'open_time'].iloc[0]),
        'last_complete_4h_close': str(bars.loc[bars.complete, 'close_time'].iloc[-1]),
        'policy': 'Exact 16 timestamp sets required; no interpolation. All partial windows excluded from indicators. Observed partial-window prices may mark positions and supply real boundary opens.',
    }
    return bars, audit, gaps, raw
