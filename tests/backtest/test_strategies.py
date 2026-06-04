"""Synthetic-fixture unit tests for all 6 backtest strategies.

Each test:
- Uses hand-crafted candle series (no network).
- Asserts that >=1 trade opens on a favorable price sequence.
- Serves as the regression guard that would have caught the Donchian 0-trades bug.

Strategy signal summary (what each test exploits):
  RSI         — closes drop → RSI < 40 (oversold) then rise → RSI > 60 (overbought)
  Bollinger   — close < lower band triggers entry; close > middle band triggers exit
  MACD        — fast EMA crosses above slow EMA (golden cross)
  EMA Cross   — 20-EMA crosses above 50-EMA (golden cross)
  Supertrend  — direction flips from -1 (bearish) to +1 (bullish)
  Donchian    — close breaks above prior period's highest high
"""
from __future__ import annotations

import pytest

from tradingview_mcp.core.services.backtest_service import (
    _run_rsi,
    _run_bollinger,
    _run_macd,
    _run_ema_cross,
    _run_supertrend,
    _run_donchian,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _candles(closes, highs=None, lows=None, opens=None):
    """Build a minimal candle list from price sequences."""
    n = len(closes)
    if highs is None:
        highs = [c * 1.01 for c in closes]
    if lows is None:
        lows = [c * 0.99 for c in closes]
    if opens is None:
        opens = closes[:]
    return [
        {
            "date":   f"2024-01-{i+1:02d}",
            "open":   opens[i],
            "high":   highs[i],
            "low":    lows[i],
            "close":  closes[i],
            "volume": 1_000_000,
        }
        for i in range(n)
    ]


# ─── RSI ──────────────────────────────────────────────────────────────────────

def test_rsi_opens_trade_on_oversold_then_overbought():
    """
    Drop hard for 20 bars (RSI < 40) then rally for 20 bars (RSI > 60).
    Expect at least 1 completed trade.
    """
    # Sharp decline: 100 → 60 over 20 bars, then recovery: 60 → 110 over 20 bars
    closes = [100 - i * 2 for i in range(20)] + [60 + i * 2.5 for i in range(20)]
    trades = _run_rsi(_candles(closes), oversold=40, overbought=60, period=14)
    assert len(trades) >= 1, f"RSI strategy produced 0 trades on oversold→overbought sequence"


def test_rsi_no_trade_on_flat_series():
    """Flat series never crosses RSI thresholds in either direction."""
    closes = [100.0] * 50
    trades = _run_rsi(_candles(closes), oversold=40, overbought=60, period=14)
    assert len(trades) == 0


# ─── Bollinger ────────────────────────────────────────────────────────────────

def test_bollinger_opens_trade_when_close_below_lower_band():
    """
    Stable base for 25 bars so bands form, then a sharp one-bar drop below the
    lower band, then recovery back above the middle band.
    """
    base = [100.0] * 25
    dip  = [85.0]           # well below lower band (100 - 2*std, std ~0 so any drop works)
    recovery = [100.0] * 10
    closes = base + dip + recovery
    trades = _run_bollinger(_candles(closes), period=20, std_mult=2.0)
    assert len(trades) >= 1, f"Bollinger produced 0 trades; expected entry on dip below lower band"


def test_bollinger_no_trade_on_flat_series():
    """Flat closes → std=0 → lower band = middle band → price never below lower band."""
    closes = [100.0] * 50
    trades = _run_bollinger(_candles(closes), period=20, std_mult=2.0)
    assert len(trades) == 0


# ─── MACD ─────────────────────────────────────────────────────────────────────

def test_macd_opens_trade_on_golden_cross():
    """
    MACD entry fires when: histogram turns from negative (MACD < signal) to
    non-negative (MACD >= signal). Pattern:
      - 35 bars flat warmup so EMA seeds converge
      - 20 bars steep decline → fast EMA drops faster → MACD goes below signal
      - 60 bars strong rally → MACD crosses above signal (entry at i=58)
      - 40 bars decline → MACD falls back below signal (exit at i=116)

    A trade is only recorded on exit; both entry AND exit must fire for len(trades) >= 1.
    """
    flat  = [100.0] * 35
    down  = [100 - i*2  for i in range(20)]    # 100 → 62 steep (histogram turns negative)
    up    = [62  + i*3  for i in range(60)]    # 62 → 239 rally (MACD crosses above signal)
    down2 = [239 - i*3  for i in range(40)]    # pullback triggers exit
    closes = flat + down + up + down2
    trades = _run_macd(_candles(closes), fast=12, slow=26, signal=9)
    assert len(trades) >= 1, f"MACD produced 0 trades; expected entry+exit on flat→down→up→down pattern"


# ─── EMA Cross ────────────────────────────────────────────────────────────────

def test_ema_cross_opens_trade_on_golden_cross():
    """
    EMA(20) crosses above EMA(50) when price reverses from downtrend to uptrend.
    Pattern:
      - 60-bar downtrend: EMA(20) stays below EMA(50)
      - 60-bar uptrend: EMA(20) rises faster, crosses EMA(50) at i=80 (golden cross)
      - 40-bar decline: EMA(20) falls below EMA(50) again (death cross = exit)

    Verified empirically: golden cross at i=80, death cross at i=145.
    """
    down  = [200.0 - i     for i in range(60)]  # 200 → 141
    up    = [140  + i * 2  for i in range(60)]  # 140 → 258  (entry at i=80)
    down2 = [258  - i * 2  for i in range(40)]  # pullback   (exit at i=145)
    closes = down + up + down2
    trades = _run_ema_cross(_candles(closes), fast_period=20, slow_period=50)
    assert len(trades) >= 1, f"EMA Cross produced 0 trades on downtrend→uptrend→downtrend golden/death cross"


def test_ema_cross_no_trade_on_monotone_decline():
    """Continuous decline: fast EMA always < slow EMA, no golden cross."""
    closes = [200 - i for i in range(80)]
    trades = _run_ema_cross(_candles(closes), fast_period=20, slow_period=50)
    assert len(trades) == 0


# ─── Supertrend ───────────────────────────────────────────────────────────────

def test_supertrend_opens_trade_on_direction_flip():
    """
    Supertrend entry fires when direction flips from -1 (bearish) to +1 (bullish).
    Exit fires when direction flips from +1 back to -1.

    Pattern:
      - 20 bars noisy decline → ATR warms up, direction = -1
      - 40 bars strong uptrend → price crosses ATR upper band → direction flips +1 (entry at i=28)
      - 30 bars steep decline → price crosses ATR lower band → direction flips -1 (exit at i=64)

    Verified empirically with direct calc_supertrend call.
    """
    n_down = 20
    dc = [100 - i * 0.5 + (3 if i % 2 == 0 else -3) for i in range(n_down)]
    dh = [c + 5 for c in dc]
    dl = [c - 5 for c in dc]

    n_up = 40
    uc = [90 + i * 4 for i in range(n_up)]   # 90 → 246
    uh = [c + 3 for c in uc]
    ul = [c - 3 for c in uc]

    n_dn2 = 30
    last_up = uc[-1]   # 246
    dc2 = [last_up - i * 6 for i in range(n_dn2)]
    dh2 = [c + 3 for c in dc2]
    dl2 = [c - 3 for c in dc2]

    closes = dc + uc + dc2
    highs  = dh + uh + dh2
    lows   = dl + ul + dl2

    trades = _run_supertrend(
        _candles(closes, highs=highs, lows=lows),
        atr_period=10, multiplier=3.0,
    )
    assert len(trades) >= 1, (
        f"Supertrend produced 0 trades; expected direction flip entry+exit on "
        f"volatile-down→strong-up→steep-down"
    )


# ─── Donchian ─────────────────────────────────────────────────────────────────

def test_donchian_opens_trade_on_breakout():
    """
    Regression guard for the confirmed bug (0 trades on every input).

    Series design:
      - 25 bars of a base range (close oscillates 95-105, highs ~106)
        → channel upper locks in at ~106 after warmup
      - 1 breakout bar: close = 120, clearly above channel upper of 106
      - Exit trigger: close drops below channel lower (< ~94)
    """
    period = 20
    # Stable base: lows ~94, highs ~106
    base_closes = [100.0] * 25
    base_highs  = [106.0] * 25
    base_lows   = [94.0]  * 25

    # Breakout bar: close = 120 > upper (106)
    breakout_close  = [120.0]
    breakout_high   = [122.0]
    breakout_low    = [118.0]

    # A few bars hovering high (position held)
    hold_closes = [118.0] * 5
    hold_highs  = [120.0] * 5
    hold_lows   = [116.0] * 5

    # Exit bar: close drops below lower band
    exit_closes = [80.0]
    exit_highs  = [82.0]
    exit_lows   = [78.0]

    closes = base_closes + breakout_close + hold_closes + exit_closes
    highs  = base_highs  + breakout_high  + hold_highs  + exit_highs
    lows   = base_lows   + breakout_low   + hold_lows   + exit_lows

    candles = _candles(closes, highs=highs, lows=lows)
    trades = _run_donchian(candles, period=period)
    assert len(trades) >= 1, (
        f"Donchian produced 0 trades on clear breakout sequence "
        f"(this is the regression guard for the inclusive-window bug)"
    )


def test_donchian_no_trade_when_close_never_breaks_channel():
    """If close never exceeds the prior period high, no entry fires."""
    period = 20
    # Monotone flat: close always equals the channel high (never strictly above it)
    closes = [100.0] * 40
    highs  = [100.0] * 40
    lows   = [90.0]  * 40
    trades = _run_donchian(_candles(closes, highs=highs, lows=lows), period=period)
    assert len(trades) == 0, "No breakout should occur when close == channel high (not strictly above)"


def test_donchian_entry_uses_prior_closed_channel_not_current_bar():
    """
    Verify the fix: if prev_high == channel upper (bar i-1 is the highest bar),
    today's close must still trigger an entry when it exceeds that channel.

    Before the fix: upper[i-1] included highs[i-1], so prev_high > upper[i-1]
    was always False, producing 0 trades.

    After the fix: we compare candles[i]["close"] > upper[i-1], which can be True
    even when candles[i-1]["high"] == upper[i-1].
    """
    period = 5
    # Warmup: 5 bars, highs all = 10.0 → channel upper after bar 4 = 10.0
    base_closes = [9.0, 9.1, 9.2, 9.3, 9.4]
    base_highs  = [10.0, 10.0, 10.0, 10.0, 10.0]  # bar 4 high == channel upper
    base_lows   = [8.0]  * 5

    # Bar 5: close = 11.0 > channel upper (10.0) → should trigger entry
    entry_close = [11.0]
    entry_high  = [11.5]
    entry_low   = [10.5]

    # Exit: close crashes below lower (8.0)
    exit_close  = [7.0]
    exit_high   = [7.5]
    exit_low    = [6.5]

    closes = base_closes + entry_close + exit_close
    highs  = base_highs  + entry_high  + exit_high
    lows   = base_lows   + entry_low   + exit_low

    trades = _run_donchian(_candles(closes, highs=highs, lows=lows), period=period)
    assert len(trades) >= 1, (
        "Donchian must fire when close > prior channel upper, "
        "even if bar i-1's high equals the channel upper (prior-channel fix)"
    )
