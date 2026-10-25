"""Signals become available at completed candle close, never at its open."""
import numpy as np
import pandas as pd

FAST = 20
SLOW = 80


def add_signals(bars: pd.DataFrame, fast=FAST, slow=SLOW) -> pd.DataFrame:
    if not 0 < fast < slow:
        raise ValueError('Require 0 < fast < slow.')
    result = bars.copy()
    complete = result.loc[result.complete, 'close']
    fast_ma = complete.rolling(fast, min_periods=fast).mean()
    slow_ma = complete.rolling(slow, min_periods=slow).mean()
    result['sma20'] = fast_ma.reindex(result.index)
    result['sma80'] = slow_ma.reindex(result.index)
    signal = pd.Series(np.nan, index=complete.index)
    available = slow_ma.notna()
    signal.loc[available & fast_ma.gt(slow_ma)] = 1
    signal.loc[available & fast_ma.lt(slow_ma)] = -1
    # Equality keeps the prior direction, including flat before the first signal.
    result['desired_at_close'] = signal.reindex(result.index).ffill().fillna(0).astype(int)
    result['signal_time_at_close'] = result.close_time.where(result.complete & result.sma80.notna()).ffill()
    result['desired_at_open'] = result.desired_at_close.shift(1).fillna(0).astype(int)
    result['signal_time_at_open'] = result.signal_time_at_close.shift(1)
    return result
