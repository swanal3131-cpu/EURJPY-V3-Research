"""Independent array accounting, separate from the trade-ledger engine."""
import numpy as np

from v3.backtest.engine import select_period


def independently_verify(bars, result, start, end, cost, benchmark_start=None):
    frame = select_period(bars, start, end)
    desired = frame.desired_at_open.to_numpy().copy()
    if benchmark_start is not None:
        desired = np.where(frame.open_time.ge(benchmark_start), 1, 0)
    actual = np.zeros(len(frame), dtype=int)
    for i in range(len(frame)):
        prior = actual[i - 1] if i else 0
        actual[i] = desired[i] if frame.open_available.iloc[i] and desired[i] else prior
    prior_positions = np.r_[0, actual[:-1]]
    prior_closes = np.r_[frame.open.iloc[0], frame.close.to_numpy()[:-1]]
    opens, closes = frame.open.to_numpy(), frame.close.to_numpy()
    # Even if no UTC boundary open exists, first observed source open followed
    # by close is a valid mark for a position already being held.
    gross_each = (prior_positions * (opens - prior_closes) + actual * (closes - opens)) / .01
    turnover = np.abs(actual - prior_positions).sum() + abs(actual[-1])
    gross, estimated_costs = float(gross_each.sum()), float(turnover * cost / 2)
    expected_net = gross - estimated_costs
    assert np.isclose(gross, result.metrics['gross_pnl_pips'], atol=1e-7, rtol=0)
    assert np.isclose(expected_net, result.metrics['net_pnl_pips'], atol=1e-7, rtol=0)
    assert np.isclose(estimated_costs, result.metrics['total_cost_pips'], atol=1e-8, rtol=0)
    assert (result.trades.entry_timestamp >= result.trades.signal_timestamp).all()
    assert (result.trades.exit_timestamp >= result.trades.entry_timestamp).all()
    assert result.equity.timestamp.is_monotonic_increasing
    return dict(independent_gross_pips=gross, independent_net_pips=expected_net,
                independent_cost_pips=estimated_costs, turnover_sides=int(turnover),
                ledger_net_pips=float(result.trades.net_pnl_pips.sum()),
                final_equity_pips=float(result.equity.net_equity_pips.iloc[-1]),
                reconciliation_passed=True)
