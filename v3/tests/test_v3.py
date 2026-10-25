"""Small, inspectable examples of timing, accounting, and input validation."""
from datetime import timedelta

import numpy as np
import pandas as pd
import pytest

from v3.backtest.engine import run_backtest, select_period
from v3.data import prepare_data
from v3.strategy.sma import add_signals


def bars(closes, opens=None, start='2018-12-01', complete=None):
    n = len(closes)
    times = pd.date_range(start, periods=n, freq='4h', tz='UTC')
    opens = closes if opens is None else opens
    return pd.DataFrame(dict(open_time=times, close_time=times + pd.Timedelta(hours=4),
                             first_source_open=times, last_source_close=times + pd.Timedelta(hours=4),
                             open=opens, close=closes, high=np.maximum(opens, closes),
                             low=np.minimum(opens, closes), source_count=16, source_hours=4.,
                             complete=True if complete is None else complete, open_available=True))


def specified(directions, prices, closes=None, start='2018-12-01'):
    b = bars(prices if closes is None else closes, prices, start)
    b['desired_at_open'] = directions
    b['signal_time_at_open'] = b.open_time - pd.Timedelta(hours=4)
    return b


def run(b, cost=0):
    return run_backtest(b, b.first_source_open.iloc[0], b.last_source_close.iloc[-1], cost)


def test_moving_average_exact_and_warmup():
    b = add_signals(bars(np.arange(1., 86.)))
    assert b.sma20.iloc[19] == pytest.approx(10.5)
    assert b.sma80.iloc[79] == pytest.approx(40.5)
    assert b.desired_at_close.iloc[:79].eq(0).all()
    assert b.desired_at_open.iloc[:80].eq(0).all()
    assert b.desired_at_open.iloc[80] == 1


@pytest.mark.parametrize('values,expected', [(range(1, 85), 1), (range(100, 16, -1), -1), ([100] * 84, 0)])
def test_direction(values, expected):
    b = add_signals(bars(list(values)))
    assert b.desired_at_close.iloc[-1] == expected


def test_equality_retains_prior_direction():
    b = add_signals(bars([1., 2., 3., 3., 3., 3.]), fast=2, slow=3)
    assert b.sma20.iloc[-1] == b.sma80.iloc[-1]
    assert b.desired_at_close.iloc[-1] == 1


def test_next_candle_open_not_signal_close():
    b = add_signals(bars([1., 2., 3., 4., 5.], [1., 2., 3., 10., 11.]), fast=2, slow=3)
    r = run(b)
    assert len(r.trades) == 1
    assert r.trades.entry_timestamp.iloc[0] == b.open_time.iloc[3]
    assert r.trades.entry_price.iloc[0] == 10


def test_prefix_signals_and_executions_unchanged_by_future():
    original = bars(np.arange(100., 220.))
    changed = original.copy()
    changed.loc[95:, ['open', 'high', 'low', 'close']] = 1.
    a, b = add_signals(original), add_signals(changed)
    pd.testing.assert_frame_equal(a.iloc[:95], b.iloc[:95])
    ra, rb = run(a), run(b)
    cutoff = original.open_time.iloc[95]
    ea = ra.equity.loc[ra.equity.timestamp.lt(cutoff) & ra.equity.event.ne('end_of_backtest')]
    eb = rb.equity.loc[rb.equity.timestamp.lt(cutoff) & rb.equity.event.ne('end_of_backtest')]
    pd.testing.assert_frame_equal(ea, eb)
    prefix = run(add_signals(original.iloc[:95]))
    pd.testing.assert_frame_equal(ea.reset_index(drop=True), prefix.equity.loc[prefix.equity.timestamp.lt(cutoff)].reset_index(drop=True))


@pytest.mark.parametrize('direction,entry,exit,expected', [(1, 120, 121, 100), (-1, 120, 119, 100), (1, 120, 119, -100), (-1, 120, 121, -100)])
def test_long_short_profit(direction, entry, exit, expected):
    r = run(specified([direction, direction], [entry, exit]))
    assert r.metrics['gross_pnl_pips'] == pytest.approx(expected)
    assert r.metrics['net_pnl_jpy'] == pytest.approx(expected * .01)


@pytest.mark.parametrize('cost', [0., 1., 1.5, 2., 3.])
def test_costs_and_reversals(cost):
    r = run(specified([1, -1, 1], [120., 121., 120.], [120.5, 120.5, 122.]), cost)
    assert list(r.trades.direction) == ['long', 'short', 'long']
    assert list(r.trades.exit_reason) == ['signal_reversal', 'signal_reversal', 'end_of_backtest']
    assert r.metrics['gross_pnl_pips'] == pytest.approx(400.)
    assert r.metrics['total_cost_pips'] == pytest.approx(3 * cost)
    assert r.metrics['net_pnl_pips'] == pytest.approx(400 - 3 * cost)
    assert r.equity.loc[r.equity.event.eq('entry'), 'cumulative_cost_pips'].iloc[0] == pytest.approx(cost / 2)
    assert r.equity.loc[r.equity.event.eq('entry'), 'cumulative_cost_pips'].iloc[1] == pytest.approx(1.5 * cost)


def test_unchanged_signal_opens_once_and_final_liquidation():
    r = run(specified([1] * 5, [120., 121., 122., 123., 124.]), 1.5)
    assert len(r.trades) == 1
    assert r.trades.exit_reason.iloc[0] == 'end_of_backtest'
    assert r.trades.exit_timestamp.iloc[0] == r.equity.timestamp.iloc[-1]
    assert r.equity.position.iloc[-1] == 0
    assert r.equity.net_equity_pips.iloc[-1] == pytest.approx(r.trades.net_pnl_pips.sum())


def test_equity_mark_to_market_drawdown_and_gap():
    b = specified([1, 1, -1], [120., 118., 121.], [122., 119., 120.])
    b.loc[2, ['open_time', 'close_time', 'first_source_open', 'last_source_close']] += pd.Timedelta(days=2)
    r = run(b, 1.5)
    assert r.metrics['max_drawdown_pips'] >= 400
    assert r.equity.net_equity_pips.iloc[-1] == pytest.approx(r.trades.net_pnl_pips.sum())
    assert r.equity.cumulative_cost_pips.iloc[-1] == 3
    assert r.metrics['calendar_exposure_pct'] == pytest.approx(100)


def write_source(tmp_path, missing=None):
    times = pd.date_range('2018-12-31T20:00Z', periods=48, freq='15min')
    raw = pd.DataFrame(dict(timestamp=times.astype(str), symbol='EUR/JPY', open=120., high=121., low=119., close=120.5, volume=0))
    if missing is not None:
        raw = raw.drop(missing)
    path = tmp_path / 'prices.csv'
    raw.to_csv(path, index=False)
    return path


def test_exact_aggregation_and_incomplete_window(tmp_path):
    path = write_source(tmp_path, missing=19)
    original = path.read_bytes()
    b, audit, gaps, raw = prepare_data(path)
    assert list(b.source_count) == [16, 15, 16]
    assert list(b.complete) == [True, False, True]
    assert audit['incomplete_4h_windows_excluded_from_sma'] == 1
    assert len(gaps) == 1
    assert b.open.iloc[0] == 120
    assert b.high.iloc[0] == 121
    assert b.low.iloc[0] == 119
    assert b.close.iloc[0] == 120.5
    assert path.read_bytes() == original


def test_incomplete_not_in_ma_and_not_future_execution_gate():
    b = bars([1., 2., 3., 100., 5.], complete=[True, True, True, False, True])
    r = add_signals(b, fast=2, slow=3)
    assert pd.isna(r.sma80.iloc[3])
    assert r.sma80.iloc[4] == pytest.approx((2 + 3 + 5) / 3)
    result = run(r)
    assert result.trades.entry_timestamp.iloc[0] == b.open_time.iloc[3]
    assert result.trades.entry_price.iloc[0] == 100


def test_missing_boundary_open_waits_until_real_open():
    b = specified([1, 1, 1], [120., 121., 122.])
    b.loc[0, 'open_available'] = False
    b.loc[0, 'first_source_open'] += pd.Timedelta(hours=2)
    result = run(b)
    assert result.trades.entry_timestamp.iloc[0] == b.open_time.iloc[1]


def test_development_evaluation_boundaries_and_history_warmup():
    b = add_signals(bars(np.arange(100., 300.), start='2018-12-15'))
    boundary = pd.Timestamp('2019-01-01', tz='UTC')
    dev = run_backtest(b, '2015-01-01', '2019-01-01', 1.5)
    evaluation = run_backtest(b, '2019-01-01', '2020-01-01', 1.5)
    assert dev.trades.exit_timestamp.max() <= boundary
    assert evaluation.trades.entry_timestamp.min() >= boundary
    assert evaluation.trades.entry_timestamp.iloc[0] == boundary
    assert evaluation.trades.signal_timestamp.iloc[0] <= boundary
    assert evaluation.equity.net_equity_pips.iloc[0] == 0
    assert len(evaluation.trades) == 1
    assert evaluation.metrics['total_cost_pips'] == 1.5


def test_no_signal_returns_defined_zeros_undefined_ratios():
    r = run(add_signals(bars([120.] * 85)))
    assert r.metrics['total_completed_trades'] == 0
    assert r.metrics['net_pnl_pips'] == 0
    assert r.metrics['profit_factor'] is None
    assert r.metrics['winning_trades_pct'] is None
    assert r.metrics['daily_return_sharpe'] is None


def test_benchmark_uses_comparable_dates_and_cost():
    b = specified([0, 1, 1], [120., 121., 123.])
    strategy = run(b, 1.5)
    benchmark = run_backtest(b, b.first_source_open.iloc[0], b.last_source_close.iloc[-1], 1.5,
                             benchmark_start=strategy.trades.entry_timestamp.iloc[0])
    assert benchmark.trades.entry_timestamp.iloc[0] == strategy.trades.entry_timestamp.iloc[0]
    assert benchmark.metrics['net_pnl_pips'] == pytest.approx(198.5)


@pytest.mark.parametrize('cost', [-1, float('nan'), float('inf')])
def test_invalid_cost_rejected(cost):
    with pytest.raises(ValueError):
        run(specified([1], [120.]), cost)


def test_raw_duplicates_invalid_prices_offgrid_rejected(tmp_path):
    path = write_source(tmp_path)
    raw = pd.read_csv(path)
    for bad in [pd.concat([raw, raw.iloc[:1]]), raw.assign(high=100.),
                raw.assign(open=float('inf'))]:
        bad.to_csv(path, index=False)
        with pytest.raises(ValueError):
            prepare_data(path)
    raw.loc[0, 'timestamp'] = '2018-12-31T20:01:00Z'
    raw.to_csv(path, index=False)
    with pytest.raises(ValueError):
        prepare_data(path)


@pytest.mark.parametrize('cost', [0., 1.5, 3.])
def test_independent_random_accounting(cost):
    from v3.audit import independently_verify
    random = np.random.default_rng(7351)
    opens = 120 + random.normal(0, .1, 200).cumsum()
    b = add_signals(bars(opens + random.normal(0, .05, 200), opens), fast=2, slow=5)
    b.loc[[7, 31, 91], 'open_available'] = False
    r = run(b, cost)
    check = independently_verify(b, r, b.first_source_open.iloc[0], b.last_source_close.iloc[-1], cost)
    assert check['reconciliation_passed']


def test_changed_current_completeness_does_not_cancel_open_order():
    b = bars([1., 2., 3., 4., 5.])
    complete = run(add_signals(b, fast=2, slow=3))
    b.loc[3:, 'complete'] = False
    partial = run(add_signals(b, fast=2, slow=3))
    assert complete.trades.entry_timestamp.iloc[0] == partial.trades.entry_timestamp.iloc[0]
    assert complete.trades.entry_price.iloc[0] == partial.trades.entry_price.iloc[0]
