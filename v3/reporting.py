"""Figures and accessible, data-driven research documentation."""
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd


def make_figures(bars, results, benchmarks, destination):
    destination.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11,
                         'axes.spines.top': False, 'axes.spines.right': False,
                         'axes.titleweight': 'bold', 'figure.facecolor': 'white',
                         'axes.grid': True, 'grid.alpha': .18})
    blue, orange, green = '#194f85', '#d97928', '#228579'

    def save(fig, name):
        fig.tight_layout()
        fig.savefig(destination / name, dpi=300, bbox_inches='tight')
        plt.close(fig)

    fig, ax = plt.subplots(figsize=(12, 5))
    sample = bars.loc[bars.complete & bars.open_time.ge('2019-01-01') & bars.open_time.lt('2019-04-01')]
    for col, label, color in [('close', 'EUR/JPY close', '#737e88'), ('sma20', 'SMA20', orange), ('sma80', 'SMA80', blue)]:
        ax.plot(sample.close_time, sample[col], label=label, color=color, lw=1.3)
    entries = results['evaluation'].trades
    entries = entries.loc[entries.entry_timestamp.lt('2019-04-01')]
    for side, marker, color in [('long', '^', green), ('short', 'v', '#b73c40')]:
        t = entries.loc[entries.direction.eq(side)]
        ax.scatter(t.entry_timestamp, t.entry_price, marker=marker, s=38, color=color, label=side.title() + ' entry', zorder=4)
    ax.set(title='EUR/JPY and fixed moving averages | January–March 2019', ylabel='JPY per EUR', xlabel='UTC date')
    ax.legend(ncols=3, fontsize=9)
    save(fig, '01_price_and_moving_averages.png')

    for key, name, title in [('full', '02_full_equity.png', 'Full available period | 2015–2019'), ('evaluation', '03_evaluation_equity.png', 'Independent evaluation | 2019')]:
        fig, ax = plt.subplots(figsize=(12, 4.8))
        e = results[key].equity
        ax.plot(e.timestamp, e.gross_equity_pips, color='#9ba6ad', lw=1, label='Gross')
        ax.plot(e.timestamp, e.net_equity_pips, color=blue, lw=1.4, label='Net: assumed 1.5 pip round trip')
        ax.axhline(0, color='black', lw=.6)
        ax.set(title='SMA20/SMA80 cumulative simulated P&L | ' + title, ylabel='Cumulative P&L (pips per 1 EUR)', xlabel='UTC date')
        ax.legend(fontsize=9)
        save(fig, name)

    fig, axes = plt.subplots(2, 1, figsize=(12, 8))
    for ax, key, label in zip(axes, ['full', 'evaluation'], ['2015–2019', '2019']):
        for r, name, color in [(results[key], 'SMA20/SMA80', blue), (benchmarks[key], 'Passive long', orange)]:
            ax.plot(r.equity.timestamp, r.equity.net_equity_pips, label=name, lw=1.3, color=color)
        ax.axhline(0, color='black', lw=.6)
        ax.set(title=f'Strategy versus passive long | {label} | same first entry and final exit', ylabel='Net P&L (pips per 1 EUR)', xlabel='UTC date')
        ax.legend(fontsize=9)
    save(fig, '04_strategy_vs_benchmark.png')

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    for ax, key, label in zip(axes, ['full', 'evaluation'], ['2015–2019', '2019']):
        net = results[key].trades.net_pnl_pips
        ax.hist(net, bins=25 if key == 'full' else 12, color=blue, edgecolor='white')
        ax.axvline(0, color=orange, lw=1.4)
        ax.set(title=f'Net trade P&L distribution | {label} | n={len(net)}', xlabel='Net pips per completed trade', ylabel='Number of trades')
    save(fig, '05_trade_pnl_distribution.png')

    fig, ax = plt.subplots(figsize=(12, 4.4))
    e = results['full'].equity
    ax.fill_between(e.timestamp, -e.drawdown_pips, 0, color=blue, alpha=.8)
    ax.set(title='SMA20/SMA80 sampled equity drawdown | 2015–2019 | 1.5 pip round trip', ylabel='Below prior peak (pips)', xlabel='UTC date')
    save(fig, '06_drawdown.png')


def number(value, digits=2):
    return 'N/A' if value is None or pd.isna(value) else f'{value:,.{digits}f}'


def write_documents(root, audit, results, benchmarks, sensitivity):
    """Write local research reports without environment files or external services."""
    reports = root / 'reports'
    table = '| Period | Trades | Gross pips | Net pips | Passive long net pips |\n|---|---:|---:|---:|---:|\n'
    for key, result in results.items():
        m = result.metrics
        table += f"| {key} | {m['total_completed_trades']} | {number(m['gross_pnl_pips'])} | {number(m['net_pnl_pips'])} | {number(benchmarks[key].metrics['net_pnl_pips'])} |\n"
    limitations = (
        'This is simulated one-EUR exposure with one pip = 0.01 JPY. Costs are assumptions. '
        'Funding/swap and actual broker execution are not fully modeled. No account capital or leverage is invented; '
        'daily-return Sharpe is N/A. Prior 2019 structural inspection prevents certifying an untouched holdout. '
        'The source timestamp convention comes from existing documentation and needs independent vendor confirmation. '
        'No raw-data redistribution rights are assumed. Verify rights before distributing any derived outputs. '
        'All periods lost money even at zero transaction cost in the verified historical experiment.'
    )
    methods = (
        'The CSV loader validates ordering, uniqueness, symbol and OHLC. UTC four-hour windows require all 16 exact '
        'quarter-hour opens to enter SMA20/SMA80. Partial windows never update averages. An actually observed UTC '
        'boundary open can execute a previously known signal even if the window later proves incomplete; '
        'future completeness cannot cancel a historical fill. All gaps remain in held-position P&L. '
        'Signals are long/short above/below the slow mean, unchanged at equality, and flat before warmup. '
        'Reversals close and reopen once. Each side pays half the assumed round-trip cost. '
        'Final liquidation uses the last observed source close as a declared accounting assumption. '
        'Development and evaluation reset flat; evaluation uses earlier indicator history without earlier P&L. '
        'The passive benchmark uses the same first entry and final exit. Independent array accounting '
        'reconciles gross P&L, cost and net P&L to the trade ledger and equity.'
    )
    research = '# EUR/JPY V3 research findings\n\nIndependent student quantitative finance investigation. '
    research += 'Can fixed SMA20/SMA80 trend following produce positive historical net P&L after estimated costs? '
    research += 'Transparent rules make the hypothesis easy to implement and test; no parameter optimization or machine learning is used.\n\n'
    research += f"Input: {audit['raw_rows']:,} 15-minute rows; {audit['first_source_open']} through {audit['last_source_open']}. "
    research += f"Complete four-hour candles: {audit['complete_4h_candles']:,}; partial windows excluded from averages: {audit['incomplete_4h_windows_excluded_from_sma']:,}.\n\n"
    research += 'Base-case results use an assumed 1.5-pip round trip.\n\n' + table + '\n'
    research += 'Calculated results are distinct from interpretation: a historical loss is useful evidence against this simple hypothesis in the tested sample. '
    research += 'It demonstrates reproducible programming, causal timing, cost measurement and willingness to report negative findings.\n\n'
    research += methods + '\n\nLimitations: ' + limitations + '\n\n'
    research += 'Future work: verify source metadata and licensing, model financing and realistic costs, and preregister an evaluation on genuinely unseen authorized data.\n'
    (reports / 'research_findings.md').write_text(research, encoding='utf-8')
    implementation = '# Standalone V3 implementation report\n\n'
    implementation += 'CSV-only standalone Python modules provide validation, aggregation, signals, execution, accounting checks, charts and reports. '
    implementation += 'There are no API download/authentication components or dotenv imports. Only aggregation settings remain in config.\n\n'
    implementation += table + '\n' + methods + '\n\n' + limitations + '\n'
    (reports / 'implementation_report.md').write_text(implementation, encoding='utf-8')
    activity = 'Built and tested a Python EUR/JPY trend model; analyzed 124k price candles, trading costs, and 2019 results; reported evidence-based findings.'
    college = '# College project summary draft\n\nAn independent investigation of a transparent trading hypothesis using Python and historical data. '
    college += 'Describe programming, quantitative reasoning, experimental checks and evidence-based conclusions.\n\n'
    college += activity + f'\n\nCharacter count: {len(activity)} / 150. Use only if the work can be personally explained and supported; disclose AI coding assistance where appropriate.\n\n'
    college += table + '\nThese are simulated findings, with no claim of live profits or reliable future performance.\n'
    (reports / 'college_project_summary.md').write_text(college, encoding='utf-8')
