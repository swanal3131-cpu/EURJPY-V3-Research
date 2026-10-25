# Final accounting review

SMA20/SMA80 and validated execution/accounting code are unchanged. All results are simulated pips for one EUR fixed base exposure; one pip is 0.01 JPY per EUR. A 1.5-pip round trip deducts 0.75 pips at entry and 0.75 at exit.

| Run | Completed trades | Long | Short | Gross pips | Cost pips | Net pips |
|---|---:|---:|---:|---:|---:|---:|
| Development 2015-2018 | 95 | 47 | 48 | −798.3 | 142.5 | −940.8 |
| Evaluation 2019 | 26 | 13 | 13 | −82.0 | 39.0 | −121.0 |
| Continuous 2015-2019 | 120 | 60 | 60 | −884.8 | 180.0 | −1,064.8 |

Counts include each final forcibly liquidated position as a completed trade. No open positions remain. Costs equal completed trades times 1.5 pips; net equals gross minus costs. Ledger sums equal final equity. Independent array accounting reconciles all 15 strategy/cost scenarios and three benchmarks: 18 checks.

## The boundary difference

Development forcibly closes its last short on December 31, 2018 at 22:00 UTC, its last observed source close. Evaluation starts flat, uses prior indicator history, and first enters short on January 2, 2019 at 00:00 UTC. Earlier P&L is excluded. The continuous run holds the same short across that boundary, from December 18, 2018 until January 21, 2019.

The development terminal short earns 212.0 gross pips; the initial evaluation short earns 102.5. Their continuous counterpart earns 310.0. The reset runs therefore omit a 4.5-pip adverse move while the continuous position remains open. Splitting also creates one extra completed trade and 1.5 extra pips of costs.

| Convention | Trades | Gross pips | Cost pips | Net pips |
|---|---:|---:|---:|---:|
| Sum of separate periods | 121 | −880.3 | 181.5 | −1,061.8 |
| Continuous full period | 120 | −884.8 | 180.0 | −1,064.8 |
| Continuous minus separate | −1 | −4.5 | −1.5 | −3.0 |

The net difference is exactly −4.5 − (−1.5) = −3.0 pips. This reflects declared horizon conventions, not missing costs or a reconciliation error. Additive calendar attribution of a continuous position would be a different report from an independent evaluation starting flat.

## Cost-sensitivity analysis

| Round-trip cost | 0 | 1 | 1.5 | 2 | 3 |
| --- | --- | --- | --- | --- | --- |
| 2015-2018 | -798.3 | -893.3 | -940.8 | -988.3 | -1,083.3 |
| 2019 | -82.0 | -108.0 | -121.0 | -134.0 | -160.0 |
| Continuous | -884.8 | -1,004.8 | -1,064.8 | -1,124.8 | -1,244.8 |

Table 2. Net strategy pips at assumed round-trip costs. Costs are estimates, not reconstructed broker spreads. No strategy parameters change across scenarios. Data: London Strategic Edge (https://londonstrategicedge.com); independent calculations.

## Other conventions

Full/development first enter January 21, 2015 at 20:00 UTC. Each passive benchmark uses its strategy's first entry and terminal exit, with one round-trip cost. Both full/evaluation terminal positions close at the last observed 2019 source close. A partial-window price may liquidate/value a position but never updates an incomplete SMA candle.

A signal's close time may equal the next candle's open time. That convention does not execute a signal at its own candle's earlier opening. Current-bar completeness never cancels a fill retrospectively.

Drawdown is sampled at observed window closes and available boundary opens, including charged costs; worse intrabar losses can be missed. Win rate/profit factor use net completed trades. Fixed-notional percentage fields are not funded-account returns; the publication uses pips. Daily-return Sharpe is N/A without an account-capital return convention.

Source: historical EUR/JPY data provided by [London Strategic Edge](https://londonstrategicedge.com); independent backtest calculations. Requested derived results are presented with permission and attribution. Raw historical price data is not redistributed.
