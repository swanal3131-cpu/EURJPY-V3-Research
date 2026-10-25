"""Run the standalone CSV-only experiment: python -m v3.run --data PATH."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform

import pandas as pd

from v3.audit import independently_verify
from v3.backtest.engine import run_backtest
from v3.data import prepare_data
from v3.strategy.sma import add_signals

PERIODS = {'development': ('2015-01-01', '2019-01-01'),
           'evaluation': ('2019-01-01', '2020-01-01'),
           'full': ('2015-01-01', '2020-01-01')}
COSTS = [0., 1., 1.5, 2., 3.]


def save_csv(frame, path):
    frame.to_csv(path, index=False, na_rep='N/A', float_format='%.10f')


def main():
    repository = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, required=True, help='Authorized local EUR/JPY 15-minute CSV; never downloaded')
    parser.add_argument('--output', type=Path, default=repository / 'local_results', help='Private generated results folder (ignored by Git)')
    args = parser.parse_args()
    destination = args.output.resolve()
    reports, figures = destination / 'reports', destination / 'figures'
    reports.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault('MPLCONFIGDIR', str(destination / '.matplotlib'))
    from v3.reporting import make_figures, write_documents

    bars, data_audit, gaps, raw = prepare_data(args.data)
    bars = add_signals(bars)
    # Save the actual missing timestamp sets for every incomplete window.
    groups = raw.groupby(raw.timestamp.dt.floor('4h'))
    missing = {}
    for start, group in groups:
        if len(group) != 16:
            expected = pd.date_range(start, periods=16, freq='15min')
            missing[start] = ';'.join(str(t) for t in expected.difference(pd.DatetimeIndex(group.timestamp)))
    bars['missing_source_opens'] = bars.open_time.map(missing).fillna('')
    save_csv(bars, reports / 'bars_and_signals.csv')
    save_csv(bars.loc[~bars.complete], reports / 'incomplete_windows.csv')
    save_csv(gaps, reports / 'source_gaps.csv')
    (reports / 'data_audit.json').write_text(json.dumps(data_audit, indent=2), encoding='utf-8')

    results, benchmarks, summary, sensitivity, checks = {}, {}, [], [], []
    for period, (start, end) in PERIODS.items():
        for cost in COSTS:
            result = run_backtest(bars, start, end, cost)
            check = independently_verify(bars, result, start, end, cost)
            checks.append(dict(period=period, model='strategy', round_trip_cost_pips=cost, **check))
            sensitivity.append(dict(period=period, **result.metrics))
            if cost == 1.5:
                results[period] = result
        base = results[period]
        if base.trades.empty:
            raise RuntimeError(f'No strategy trades in {period}; no comparable benchmark can be formed. Review source coverage.')
        benchmark = run_backtest(bars, start, end, 1.5, benchmark_start=base.trades.entry_timestamp.iloc[0])
        checks.append(dict(period=period, model='passive_long', round_trip_cost_pips=1.5,
                           **independently_verify(bars, benchmark, start, end, 1.5, base.trades.entry_timestamp.iloc[0])))
        benchmarks[period] = benchmark
        for model, result in [('strategy', base), ('passive_long', benchmark)]:
            summary.append(dict(period=period, model=model, **result.metrics))
            save_csv(result.equity, reports / f'equity_{period}_{model}.csv')
            save_csv(result.trades, reports / f'trades_{period}_{model}.csv')
        save_csv(pd.DataFrame([base.metrics]), reports / f'{period}_results.csv')
        print(f"{period}: {len(base.trades)} trades; gross {base.metrics['gross_pnl_pips']:.2f}; net {base.metrics['net_pnl_pips']:.2f} pips; passive {benchmark.metrics['net_pnl_pips']:.2f}")

    summary, sensitivity, checks = pd.DataFrame(summary), pd.DataFrame(sensitivity), pd.DataFrame(checks)
    save_csv(summary, reports / 'performance_summary.csv')
    save_csv(sensitivity, reports / 'cost_sensitivity.csv')
    save_csv(checks, reports / 'reconciliation.csv')
    save_csv(results['full'].trades, reports / 'trade_log.csv')
    manifest = dict(python=platform.python_version(),
                    dependencies={p: importlib.metadata.version(p) for p in ['pandas', 'numpy', 'matplotlib']},
                    input_sha256=data_audit['source_sha256'], parameters=dict(fast_sma=20, slow_sma=80, pip_jpy=.01, base_units_eur=1, costs_round_trip_pips=COSTS),
                    periods=PERIODS,
                    source_sha256={str(p.relative_to(repository)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest()
                                   for p in [*(repository / 'v3').rglob('*.py'),
                                             repository / 'data/data_loader.py',
                                             repository / 'data/validation.py',
                                             repository / 'data/aggregation.py',
                                             repository / 'config/backtest_config.py']
                                   if '__pycache__' not in p.parts})
    (reports / 'run_manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    make_figures(bars, results, benchmarks, figures)
    write_documents(destination, data_audit, results, benchmarks, sensitivity)
    print(f"Validated {data_audit['raw_rows']:,} rows; {data_audit['complete_4h_candles']:,} complete 4h candles; {len(checks)} independent reconciliations passed.")
    print(f'Results saved to {destination}')


if __name__ == '__main__':
    main()
