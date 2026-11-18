# Deep-oversold bounce bot for make.fun btc-race-24h-20261118-1444.
#
# Strategy (long only, one asset CBBTC, 1-minute bars):
#   Buy only the deepest oversold bounces, then take a quick profit.
#   - RSI(14, Wilder's) crosses back above 30 (a recovery after being oversold),
#   - the close is above the lower Bollinger Band (30 typical prices, 2 sigma),
#   - and RSI dipped below 15 at some point in the last 15 bars (deep oversold).
#   That last filter is the edge: shallow oversold signals fire constantly in a
#   falling market and bleed fees; only the deep ones precede real bounces.
#   A 30-bar Bollinger (vs 20) smooths the band so the bounce is not rejected
#   by a fast-falling lower band; deepening the filter to 15 drops the one
#   marginal trade that lost money on the dev window.
#   Position: 65% of cash (keeps price impact low vs a full-size order, and
#   caps the loss on a flat trade to under $1 on the dev window).
#   Exit the whole position when any of these holds at a bar's close:
#   - value/cost >= 1.0056 (take profit, about +0.6% over the fill),
#   - value/cost <= 0.9956 (stop loss, about -0.4% under the fill),
#   - held for 15 bars (the bounce peaks around 10-15 bars, then fades;
#     holding to 20 only adds drift losses),
#   - RSI >= 80 (overbought; the standard 80 level lets a strong bounce run
#     a few bars longer than 75 did).
#   Dev window (1,440 bars): net PnL +$8.99, 4 round trips, maxDD 0.19%,
#   quarter split +$7.80 / $0.00 / +$2.07 / -$0.87. It never holds through a
#   sustained decline, so it stays in cash while the market grinds down.
#   Parameters chosen by grid search over the dev window (work/grid7*.py),
#   kept on a plateau, not a spike: size 0.62-0.68 x hold 12-15 all pass.
#   Rejected by the same search: ATR-based TP/SL (far too tight on 1-min
#   bars), trailing exits (never fire), EMA9/EMA-cross entry filters (they
#   kill the counter-trend bounce), size 1.0 (pumps Q1 but worst quarter
#   -$2.20).
#
# Method adapted from the Agensi technical-scanner skill (EMA/RSI/MACD/Bollinger/
# ATR/ADX regime method, applied here to 1-minute bars): use RSI + Bollinger
# for the oversold-bounce entry and a short hold, and stay out during a clear
# downtrend unless the oversold signal is deep. No skill text is copied here.
#
# Standard library only. Deterministic: no clock, no environment, no random.
# State is kept in module-level variables; every run on the same bars gives
# the same orders.

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars

SYMBOL = "CBBTC"

RSI_BARS = 14
BAND_BARS = 30
BAND_SIGMAS = 2.0
RSI_RECOVER = 30.0        # entry: RSI crosses back above this
RSI_DEEP = 15.0
DEEP_LOOKBACK = 15        # bars to look back for the deep dip
RSI_EXIT_ABOVE = 80.0     # exit: RSI overbought
TAKE_PROFIT_NUM = 10056  # value/cost >= 1.0056, i.e. close/fill >= 1.006
TAKE_PROFIT_DEN = 10000   # (cost carries the 4 bps buy fee, so the ratio
STOP_LOSS_NUM = 9956      #  is 0.9996x the price ratio; these thresholds
STOP_LOSS_DEN = 10000     #  reproduce a +0.6% TP / -0.4% SL on the fill)
MAX_HOLD_BARS = 15
SIZE_NUM = 13             # buy 13/20 of cash (65%)
SIZE_DEN = 20
MAX_SLIPPAGE_BPS = 100


class Series:
    """Per-symbol indicator state, updated bar by bar."""

    def __init__(self):
        self.typical = []       # last BAND_BARS typical prices, oldest first
        self.last_close = None  # previous close (float)
        self.first_changes = []  # first RSI_BARS changes, until averages are set
        self.gain = None        # Wilder's average gain
        self.loss = None        # Wilder's average loss
        self.prev_rsi = None    # RSI of the previous bar
        self.rsi_history = []   # last DEEP_LOOKBACK RSI values, oldest first
        self.entry_seq = None   # seq of the batch where the position first appeared


SERIES = {}


def _push(bar):
    s = SERIES.get(bar["symbol"])
    if s is None:
        SERIES[bar["symbol"]] = s = Series()
    c = float(bar["c"])
    s.typical.append((float(bar["h"]) + float(bar["l"]) + c) / 3.0)
    if len(s.typical) > BAND_BARS:
        s.typical.pop(0)
    if s.last_close is not None:
        change = c - s.last_close
        up = change if change > 0 else 0.0
        down = -change if change < 0 else 0.0
        if s.gain is None or s.loss is None:
            s.first_changes.append(change)
            if len(s.first_changes) == RSI_BARS:
                s.gain = sum(x for x in s.first_changes if x > 0) / RSI_BARS
                s.loss = sum(-x for x in s.first_changes if x < 0) / RSI_BARS
        else:
            s.gain = (s.gain * (RSI_BARS - 1) + up) / RSI_BARS
            s.loss = (s.loss * (RSI_BARS - 1) + down) / RSI_BARS
    s.last_close = c
    return s


def _rsi(s):
    if s.gain is None or s.loss is None:
        return None
    moved = s.gain + s.loss
    if moved == 0:
        return 50.0
    return 100.0 * s.gain / moved


def _lower_band(s):
    if len(s.typical) < BAND_BARS:
        return None
    mean = sum(s.typical) / BAND_BARS
    var = sum((x - mean) * (x - mean) for x in s.typical) / BAND_BARS
    return mean - BAND_SIGMAS * (var ** 0.5)


def on_batch(state, batch):
    for bar in batch["bars"]:
        _push(bar)
    if state.warming_up:
        return []
    s = SERIES.get(SYMBOL)
    if s is None:
        return []
    # Only act on a fresh bar for our symbol.
    if not any(b["symbol"] == SYMBOL for b in batch["bars"]):
        return []
    r = _rsi(s)
    if r is None:
        return []
    # Record this bar's RSI for the deep-oversold lookback.
    s.rsi_history.append(r)
    if len(s.rsi_history) > DEEP_LOOKBACK:
        s.rsi_history.pop(0)

    held = state.positions.get(SYMBOL)
    close = state.close(SYMBOL)
    if held is not None:
        if s.entry_seq is None:
            s.entry_seq = state.seq
        # Exit checks.
        value = state.value(SYMBOL, held.qty)
        cost = held.cost
        exit_now = False
        if cost > 0:
            if value * TAKE_PROFIT_DEN >= cost * TAKE_PROFIT_NUM:
                exit_now = True
            elif value * STOP_LOSS_DEN <= cost * STOP_LOSS_NUM:
                exit_now = True
        if not exit_now and r >= RSI_EXIT_ABOVE:
            exit_now = True
        if not exit_now and state.seq - s.entry_seq >= MAX_HOLD_BARS:
            exit_now = True
        if exit_now:
            s.entry_seq = None
            return [{"side": "sell", "symbol": SYMBOL, "qty": held.qty,
                     "max_slippage_bps": MAX_SLIPPAGE_BPS}]
        s.prev_rsi = r
        return []

    # Flat: look for the deep-oversold bounce entry.
    s.entry_seq = None
    prev = s.prev_rsi
    s.prev_rsi = r
    if prev is None:
        return []
    if not (prev < RSI_RECOVER <= r):
        return []
    lower = _lower_band(s)
    if lower is None or close is None or close < lower:
        return []
    if not any(x < RSI_DEEP for x in s.rsi_history):
        return []
    # Buy 65% of cash, within the weight cap and the minimum notional.
    room = state.weight_room(SYMBOL)
    spend = state.cash * SIZE_NUM // SIZE_DEN
    if spend > room:
        spend = room
    if spend < int(state.hello["fees"]["min_notional_quote_units"]):
        return []
    return [{"side": "buy", "symbol": SYMBOL,
             "notional_quote_units": spend,
             "max_slippage_bps": MAX_SLIPPAGE_BPS}]


if __name__ == "__main__":
    makefun_bars.run(on_batch)
