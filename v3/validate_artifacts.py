"""Independently inspect saved CSVs, source aggregation, hashes, and PNGs.

Run after v3.run: python -m v3.validate_artifacts --data PATH
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image


def validate(repository, output, data):
    reports = output / 'reports'
    audit = json.loads((reports / 'data_audit.json').read_text(encoding='utf-8'))
    manifest = json.loads((reports / 'run_manifest.json').read_text(encoding='utf-8'))
    assert hashlib.sha256(data.read_bytes()).hexdigest() == audit['source_sha256'] == manifest['input_sha256']
    for relative, expected in manifest['source_sha256'].items():
        assert hashlib.sha256((repository / relative).read_bytes()).hexdigest() == expected, relative
    summary = pd.read_csv(reports / 'performance_summary.csv')
    sensitivity = pd.read_csv(reports / 'cost_sensitivity.csv')
    rec = pd.read_csv(reports / 'reconciliation.csv')
    assert len(summary) == 6 and len(sensitivity) == 15 and len(rec) == 18
    assert rec.reconciliation_passed.all()
    for period in ['development', 'evaluation', 'full']:
        cases = sensitivity.loc[sensitivity.period.eq(period)]
        assert set(cases.round_trip_cost_pips) == {0., 1., 1.5, 2., 3.}
        assert cases.total_completed_trades.nunique() == 1
        assert np.allclose(cases.gross_pnl_pips, cases.gross_pnl_pips.iloc[0], atol=1e-8)
        assert np.allclose(cases.net_pnl_pips, cases.gross_pnl_pips - cases.total_completed_trades * cases.round_trip_cost_pips, atol=1e-8)
        entry_dates = []
        for model in ['strategy', 'passive_long']:
            row = summary.loc[summary.period.eq(period) & summary.model.eq(model)].iloc[0]
            t = pd.read_csv(reports / f'trades_{period}_{model}.csv')
            q = pd.read_csv(reports / f'equity_{period}_{model}.csv')
            entry, exit = pd.to_datetime(t.entry_timestamp, utc=True), pd.to_datetime(t.exit_timestamp, utc=True)
            signal = pd.to_datetime(t.signal_timestamp, utc=True)
            entry_dates.append((entry.iloc[0], exit.iloc[-1]))
            direction = np.where(t.direction.eq('long'), 1., -1.)
            assert np.allclose(direction * (t.exit_price - t.entry_price) / .01, t.gross_pnl_pips, atol=1e-7)
            assert np.allclose(t.gross_pnl_pips - t.transaction_cost_pips, t.net_pnl_pips, atol=1e-8)
            assert np.allclose(t.net_pnl_jpy, t.net_pnl_pips * .01, atol=1e-8)
            assert np.allclose((exit - entry).dt.total_seconds() / 3600, t.holding_hours, atol=1e-8)
            assert (signal <= entry).all() and (entry <= exit).all()
            assert (entry.dt.hour % 4 == 0).all() and entry.dt.minute.eq(0).all()
            assert t.exit_reason.iloc[-1] == 'end_of_backtest'
            assert t.exit_reason.iloc[:-1].eq('signal_reversal').all()
            assert int(q.position.iloc[-1]) == 0
            assert pd.to_datetime(q.timestamp, utc=True).is_monotonic_increasing
            assert np.isclose(t.net_pnl_pips.sum(), row.net_pnl_pips, atol=1e-7)
            assert np.isclose(t.net_pnl_pips.sum(), q.net_equity_pips.iloc[-1], atol=1e-7)
            assert np.isclose(t.transaction_cost_pips.sum(), row.total_cost_pips, atol=1e-8)
            assert np.allclose(q.gross_equity_pips, q.realized_gross_pips + q.unrealized_gross_pips, atol=1e-7)
            assert np.allclose(q.net_equity_pips, q.gross_equity_pips - q.cumulative_cost_pips, atol=1e-7)
            assert np.isclose(q.drawdown_pips.max(), row.max_drawdown_pips, atol=1e-7)
            if period == 'development':
                assert entry.min() >= pd.Timestamp('2015-01-01', tz='UTC')
                assert exit.max() <= pd.Timestamp('2019-01-01', tz='UTC')
            if period == 'evaluation':
                assert entry.min() >= pd.Timestamp('2019-01-01', tz='UTC')
                assert exit.max() <= pd.Timestamp('2020-01-01', tz='UTC')
        assert entry_dates[0] == entry_dates[1]

    # Separate pandas grouping checks all exported OHLC and completeness fields.
    raw = pd.read_csv(data)
    raw['timestamp'] = pd.to_datetime(raw.timestamp, utc=True)
    b = pd.read_csv(reports / 'bars_and_signals.csv')
    independent = raw.groupby(raw.timestamp.dt.floor('4h')).agg(open=('open', 'first'), high=('high', 'max'), low=('low', 'min'), close=('close', 'last'), source_count=('open', 'size'))
    assert len(raw) == audit['raw_rows'] and len(b) == len(independent)
    assert not raw.timestamp.duplicated().any()
    assert pd.DatetimeIndex(pd.to_datetime(b.open_time, utc=True)).equals(independent.index.rename('open_time'))
    for col in ['open', 'high', 'low', 'close', 'source_count']:
        assert np.allclose(b[col], independent[col], atol=1e-9, rtol=0)
    completeness = dict(zip(pd.to_datetime(b.open_time, utc=True), b.complete))
    for index, group in raw.groupby(raw.timestamp.dt.floor('4h')):
        exact = pd.DatetimeIndex(group.timestamp).equals(pd.date_range(index, periods=16, freq='15min'))
        assert bool(completeness[index]) == exact
    complete_closes = b.loc[b.complete, 'close']
    for window, name in [(20, 'sma20'), (80, 'sma80')]:
        expected = complete_closes.rolling(window, min_periods=window).mean().reindex(b.index)
        assert np.allclose(expected, b[name], atol=1e-8, equal_nan=True, rtol=0)
    assert b.loc[~b.complete, ['sma20', 'sma80']].isna().all().all()
    assert len(pd.read_csv(reports / 'incomplete_windows.csv')) == audit['incomplete_4h_windows_excluded_from_sma']

    images = []
    for p in sorted((output / 'figures').glob('*.png')):
        with Image.open(p) as im:
            im.verify()
        with Image.open(p) as im:
            assert im.width >= 3000 and im.height >= 1000
            assert im.info['dpi'][0] >= 299
            images.append(dict(file=p.name, width=im.width, height=im.height, dpi=im.info['dpi']))
    assert len(images) == 6
    required = ['implementation_report.md', 'research_findings.md', 'college_project_summary.md',
                'performance_summary.csv', 'development_results.csv', 'evaluation_results.csv',
                'trade_log.csv', 'cost_sensitivity.csv']
    for name in required:
        assert (reports / name).stat().st_size > 0, name
    result = dict(passed=True, validated_strategy_benchmark_runs=6, independent_reconciliations=18,
                  independent_ohlc_windows=len(independent), raw_rows=len(raw),
                  source_hashes_current=True, images=images,
                  notes='Automated numeric, source hash, PNG integrity and resolution checks passed. Visual inspection is separate.')
    (reports / 'artifact_validation.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'images'}, indent=2))


def main():
    repository = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=repository / 'local_results')
    parser.add_argument('--data', type=Path, required=True, help='Same authorized local CSV used by v3.run')
    args = parser.parse_args()
    validate(repository, args.output, args.data)


if __name__ == '__main__':
    main()
