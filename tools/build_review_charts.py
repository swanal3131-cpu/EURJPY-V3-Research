"""Build three review figures from private results, without exporting prices."""
import argparse
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd

def build(results, output):
    output.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'axes.spines.top': False,
                         'axes.spines.right': False, 'axes.titleweight': 'bold', 'axes.grid': True, 'grid.alpha': .18})
    blue, orange = '#194f85', '#c96922'
    footer = 'Simulated one-EUR exposure | Data: London Strategic Edge (londonstrategicedge.com)'
    for period, title, filename in [('full', 'Continuous backtest 2015-2019', 'full_period_comparison.png'),
                                    ('evaluation', 'Independent evaluation 2019', 'evaluation_comparison.png')]:
        fig, ax = plt.subplots(figsize=(10, 4.4))
        for model, label, color in [('strategy', 'SMA20/SMA80', blue), ('passive_long', 'Passive long', orange)]:
            e = pd.read_csv(results / 'reports' / f'equity_{period}_{model}.csv', usecols=['timestamp', 'net_equity_pips'])
            ax.plot(pd.to_datetime(e.timestamp, utc=True), e.net_equity_pips, label=label, lw=1.25, color=color)
        ax.axhline(0, color='black', lw=.7)
        ax.set(title=title + ' | assumed 1.5-pip round trip', xlabel='UTC date', ylabel='Cumulative net P&L (pips)')
        ax.legend(fontsize=9)
        fig.text(.5, .015, footer, ha='center', fontsize=8, color='#555555')
        fig.tight_layout(rect=[0, .045, 1, 1])
        fig.savefig(output / filename, dpi=300)
        plt.close(fig)
    costs = pd.read_csv(results / 'reports/cost_sensitivity.csv')
    fig, ax = plt.subplots(figsize=(10, 4.4))
    for key, name, color in [('development', '2015-2018', blue), ('evaluation', '2019', '#287e67'), ('full', 'Continuous 2015-2019', orange)]:
        sample = costs.loc[costs.period.eq(key)].sort_values('round_trip_cost_pips')
        ax.plot(sample.round_trip_cost_pips, sample.net_pnl_pips, marker='o', label=name, color=color)
    ax.axhline(0, color='black', lw=.7)
    ax.set(title='Cost sensitivity | all tested periods remain negative', xlabel='Assumed round-trip cost (pips per trade)',
           ylabel='Total net strategy P&L (pips)', xticks=[0, 1, 1.5, 2, 3])
    ax.legend(fontsize=9)
    fig.text(.5, .015, footer, ha='center', fontsize=8, color='#555555')
    fig.tight_layout(rect=[0, .045, 1, 1])
    fig.savefig(output / 'cost_sensitivity.png', dpi=300)
    plt.close(fig)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', type=Path, default=Path('local_results'))
    parser.add_argument('--output', type=Path, default=Path('docs/figures'))
    args = parser.parse_args()
    build(args.results, args.output)
