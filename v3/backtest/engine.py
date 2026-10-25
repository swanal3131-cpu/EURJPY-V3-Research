"""One EUR base unit, JPY quote P&L, and one pip = 0.01 JPY.

Execution consumes only lagged signals and the current boundary open, with no
dependency on current-bar completeness or close. Partial-window prices are used
only when actually observed. Every change in cash and inventory is journaled.
"""
from dataclasses import dataclass
import math

import numpy as np
import pandas as pd

PIP = 0.01
TRADE_COLUMNS = ['trade_number', 'direction', 'signal_timestamp', 'entry_timestamp',
                 'entry_price', 'exit_timestamp', 'exit_price', 'gross_pnl_pips',
                 'transaction_cost_pips', 'net_pnl_pips', 'gross_pnl_jpy',
                 'net_pnl_jpy', 'holding_hours', 'exit_reason']


def utc(value):
    t = pd.Timestamp(value)
    return t.tz_localize('UTC') if t.tzinfo is None else t.tz_convert('UTC')


@dataclass
class Result:
    trades: pd.DataFrame
    equity: pd.DataFrame
    metrics: dict


def select_period(bars, start, end):
    """[start, end), with no outside observations or P&L included."""
    lo, hi = utc(start), utc(end)
    if lo >= hi:
        raise ValueError('start must precede end')
    return bars.loc[bars.first_source_open.ge(lo) & bars.last_source_close.le(hi)].copy()


def run_backtest(bars, start, end, round_trip_pips=1.5, benchmark_start=None):
    if not math.isfinite(round_trip_pips) or round_trip_pips < 0:
        raise ValueError('Round-trip costs must be finite and nonnegative.')
    frame = select_period(bars, start, end)
    if frame.empty:
        raise ValueError('No observations in the requested period.')
    benchmark = benchmark_start is not None
    entry = None
    position = 0
    realized = costs = 0.0
    half_cost = round_trip_pips / 2
    trades, events = [], []
    exposed_hours = long_hours = short_hours = 0.0

    def mark(timestamp, price, event):
        unrealized = position * (price - entry['price']) / PIP if entry else 0.0
        gross = realized + unrealized
        events.append(dict(timestamp=timestamp, event=event, price=price,
                           position=position, realized_gross_pips=realized,
                           unrealized_gross_pips=unrealized, cumulative_cost_pips=costs,
                           gross_equity_pips=gross, net_equity_pips=gross - costs))

    def close(timestamp, price, reason):
        nonlocal realized, costs, entry, position
        gross = position * (price - entry['price']) / PIP
        realized += gross
        costs += half_cost
        trades.append(dict(
            trade_number=len(trades) + 1, direction='long' if position == 1 else 'short',
            signal_timestamp=entry['signal_time'], entry_timestamp=entry['time'],
            entry_price=entry['price'], exit_timestamp=timestamp, exit_price=price,
            gross_pnl_pips=gross, transaction_cost_pips=round_trip_pips,
            net_pnl_pips=gross - round_trip_pips, gross_pnl_jpy=gross * PIP,
            net_pnl_jpy=(gross - round_trip_pips) * PIP,
            holding_hours=(timestamp - entry['time']).total_seconds() / 3600,
            exit_reason=reason))
        entry = None
        position = 0
        mark(timestamp, price, reason)

    first = frame.iloc[0]
    mark(first.first_source_open, first.open, 'initial_flat')
    for row in frame.itertuples():
        if row.open_available:
            # Valuing the old position here includes all overnight/weekend gaps.
            mark(row.open_time, row.open, 'pre_execution_open')
            desired = (1 if row.open_time >= utc(benchmark_start) else 0) if benchmark else row.desired_at_open
            if desired and desired != position:
                if not benchmark and (pd.isna(row.signal_time_at_open) or row.signal_time_at_open > row.open_time):
                    raise AssertionError('Execution attempted before signal availability.')
                if position:
                    close(row.open_time, row.open, 'signal_reversal')
                costs += half_cost
                position = int(desired)
                entry = dict(time=row.open_time, price=row.open,
                             signal_time=row.open_time if benchmark else row.signal_time_at_open)
                mark(row.open_time, row.open, 'entry')
        if position:
            exposed_hours += row.source_hours
            long_hours += row.source_hours if position == 1 else 0
            short_hours += row.source_hours if position == -1 else 0
        mark(row.last_source_close, row.close, 'observed_close')
    # Predetermined horizon liquidation at the final observed 15m close.
    # It is an accounting/execution assumption, not an SMA signal or next-open fill.
    if entry:
        close(frame.iloc[-1].last_source_close, frame.iloc[-1].close, 'end_of_backtest')
    ledger = pd.DataFrame(trades, columns=TRADE_COLUMNS)
    equity = pd.DataFrame(events)
    equity['net_equity_jpy'] = equity.net_equity_pips * PIP
    equity['drawdown_pips'] = equity.net_equity_pips.cummax().clip(lower=0) - equity.net_equity_pips
    final = equity.iloc[-1]
    for col, target in [('net_pnl_pips', final.net_equity_pips),
                        ('gross_pnl_pips', final.gross_equity_pips),
                        ('transaction_cost_pips', final.cumulative_cost_pips)]:
        if not np.isclose(ledger[col].sum(), target, atol=1e-8, rtol=0):
            raise AssertionError(f'Ledger reconciliation failed: {col}')
    metrics = summarize(ledger, equity)
    metrics.update(
        requested_start=str(utc(start)), requested_end_exclusive=str(utc(end)),
        observed_start=str(first.first_source_open), observed_end=str(frame.iloc[-1].last_source_close),
        first_entry=str(ledger.entry_timestamp.iloc[0]) if len(ledger) else None,
        round_trip_cost_pips=round_trip_pips,
        observed_hours=float(frame.source_hours.sum()),
        directional_exposure_pct=100 * exposed_hours / frame.source_hours.sum(),
        long_exposure_pct=100 * long_hours / frame.source_hours.sum(),
        short_exposure_pct=100 * short_hours / frame.source_hours.sum(),
        calendar_exposure_pct=100 * ledger.holding_hours.sum() / ((frame.iloc[-1].last_source_close - first.first_source_open).total_seconds() / 3600),
        daily_return_sharpe=None,
        sharpe_note='N/A: no funded account capital or portfolio return denominator specified. Fixed-unit P&L is not an account return.',
        end_open_positions=0,
    )
    return Result(ledger, equity, metrics)


def summarize(trades, equity):
    n = len(trades)
    net = trades.net_pnl_pips.astype(float)
    winners, losers = net[net > 0], net[net < 0]
    losing_streak = longest = 0
    for pnl in net:
        losing_streak = losing_streak + 1 if pnl < 0 else 0
        longest = max(longest, losing_streak)
    notional = float(trades.entry_price.iloc[0]) if n else None
    return dict(
        total_completed_trades=n, long_trades=int(trades.direction.eq('long').sum()),
        short_trades=int(trades.direction.eq('short').sum()),
        average_holding_hours=float(trades.holding_hours.mean()) if n else None,
        winning_trades_pct=100 * len(winners) / n if n else None,
        gross_pnl_pips=float(trades.gross_pnl_pips.sum()),
        net_pnl_pips=float(net.sum()), total_cost_pips=float(trades.transaction_cost_pips.sum()),
        net_pnl_jpy=float(net.sum()) * PIP,
        average_net_pips=float(net.mean()) if n else None,
        average_winning_pips=float(winners.mean()) if len(winners) else None,
        average_losing_pips=float(losers.mean()) if len(losers) else None,
        profit_factor=float(winners.sum() / -losers.sum()) if len(losers) else None,
        best_trade_pips=float(net.max()) if n else None,
        worst_trade_pips=float(net.min()) if n else None,
        max_drawdown_pips=float(equity.drawdown_pips.max()),
        longest_losing_streak=longest,
        initial_one_eur_notional_jpy=notional,
        pnl_pct_initial_notional=100 * float(net.sum()) * PIP / notional if n else None,
        max_drawdown_jpy=float(equity.drawdown_pips.max()) * PIP,
    )
