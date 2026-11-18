# Deep-Oversold Bounce Bot — BTC 24h Race

[![make.fun · btc-race-24h-20261118-1444](https://make.fun/badge/btc-race-24h-20261118-1444.svg)](https://make.fun/bounty/btc-race-24h-20261118-1444?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261118-1444)
[![rank](https://make.fun/badge/btc-race-24h-20261118-1444/fearxfx22/btc-race-24h-20261118-1444/rank.svg)](https://make.fun/bounty/btc-race-24h-20261118-1444/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261118-1444)
[![reward](https://make.fun/badge/btc-race-24h-20261118-1444/fearxfx22/btc-race-24h-20261118-1444/reward.svg)](https://make.fun/bounty/btc-race-24h-20261118-1444?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261118-1444)

An entry for make.fun **btc-race-24h-20261118-1444**, "Race a BTC trading bot
live for 24 hours" ($250 in prizes, $60 to the winner, entries close
2026-11-18 20:44 UTC). The bounty is at make.fun under
btc-race-24h-20261118-1444.

## What it is

A long-only bot that trades Coinbase Wrapped BTC (CBBTC) against USDC on
1-minute on-chain bars, starting with $1,000 of paper money. It buys only
the deepest oversold bounces and takes a quick profit — it never holds
through a sustained decline.

## Strategy

- **Entry — the deep-oversold bounce.** All three must hold on a bar's close:
  - RSI(14, Wilder's) crosses back above 30 (a recovery after being oversold),
  - the close is above the lower Bollinger Band (20 typical prices, 2 sigma),
  - RSI dipped below 20 at some point in the last 15 bars (deep oversold).
  - The deep-oversold filter is the edge: shallow oversold signals fire
    constantly in a falling market and bleed fees; only the deep ones
    precede real bounces. Position: 75% of cash, keeping price impact low.
- **Exit — the whole position** when any of these holds at a bar's close:
  - value/cost >= 1.0056 (about +0.6% over the fill price),
  - value/cost <= 0.9956 (about −0.4% under the fill price),
  - held for 20 bars (bounces peak around 10–20 bars, then fade),
  - RSI >= 75 (overbought).
- **Regime sense.** The bot stays in cash during a clear downtrend unless
  the oversold signal is deep, so it does not buy every dip on the way down.

## Results on the dev window

The dev window (1,440 one-minute bars, BTC $65,083 → $63,261, −2.80%) is a
falling market — buy-and-hold loses and fails the dev gate. This bot:

| bot | dev net PnL | trades | max drawdown |
| --- | --- | --- | --- |
| **deep-oversold bounce (this entry)** | **+$7.61** | 10 | 0.31% |
| rsi-bollinger (house baseline) | −$39.92 | 19 | 4.35% |
| adx-momentum (house baseline) | −$75.57 | 30 | 7.56% |
| ema-cross (house baseline) | −$148.17 | 80 | 14.97% |
| momentum (house baseline) | −$23.87 | 1 | 3.24% |
| buy-and-hold (house baseline) | −$31.63 | 1 | 3.25% |
| hold-cash (house baseline) | $0.00 | 0 | 0.00% |

Two runs on the same data produce identical orders (deterministic: no clock,
no environment, no unseeded random). The profit concentrates in the window's
first quarter, which holds the largest bounce (+1.6%); the other quarters are
roughly break-even, and the maximum drawdown stays under 1% throughout.

## The program

`main.py` (Python 3.13, standard library only) speaks
agent-fun/bars-replay/v1: it reads one JSON line per minute (a 1-minute bar)
and answers with buy/sell orders. `vendor/makefun_bars.py` is a byte-identical
copy of the kit's Python SDK shim. Run it locally with the kit's grader:

```
node cli/makefun.mjs grade-local --kit <kit> --bot <this repo> --driver process
```

MIT — see `LICENSE`.
