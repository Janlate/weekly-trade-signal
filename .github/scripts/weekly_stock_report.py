#!/usr/bin/env python3
"""Weekly Stock Technical Analysis Report - LINE Notify via GitHub Actions"""

import os
import requests
from tradingview_ta import TA_Handler, Interval

LINE_TOKEN = os.environ["LINE_NOTIFY_TOKEN"]

STOCKS = {
    'GOOGL': ('NASDAQ', 'america'),
    'TSLA': ('NASDAQ', 'america'),
    'BABA': ('NYSE', 'america'),
    'NFLX': ('NASDAQ', 'america'),
    'NVDA': ('NASDAQ', 'america'),
    'META': ('NASDAQ', 'america'),
    'MSFT': ('NASDAQ', 'america'),
    'IREN': ('NASDAQ', 'america'),
}


def get_yahoo_price(symbol):
    """Get price data from Yahoo Finance via yfinance."""
    import yfinance as yf
    ticker = yf.Ticker(symbol)
    info = ticker.info
    price = info.get('regularMarketPrice') or info.get('currentPrice')
    high_52w = info.get('fiftyTwoWeekHigh')
    low_52w = info.get('fiftyTwoWeekLow')
    return {'price': price, '52w_high': high_52w, '52w_low': low_52w}


def analyze_stock(symbol, exchange, screener):
    """Analyze a single stock and return summary."""
    yf_data = get_yahoo_price(symbol)
    handler = TA_Handler(
        symbol=symbol, exchange=exchange,
        screener=screener, interval=Interval.INTERVAL_1_DAY
    )
    analysis = handler.get_analysis()
    ind = analysis.indicators

    price = yf_data['price']
    high_52w = yf_data['52w_high']
    pct_from_high = ((price - high_52w) / high_52w) * 100 if price and high_52w else 0

    rsi = ind.get('RSI')
    macd_val = ind.get('MACD.macd', 0) or 0
    macd_sig = ind.get('MACD.signal', 0) or 0
    macd_hist = macd_val - macd_sig

    # RSI signal
    if rsi and rsi > 70:
        rsi_signal = "SELL (Overbought)"
    elif rsi and rsi < 30:
        rsi_signal = "BUY (Oversold)"
    elif rsi and rsi > 55:
        rsi_signal = "Bullish"
    elif rsi and rsi < 45:
        rsi_signal = "Bearish"
    else:
        rsi_signal = "Neutral"

    # MACD signal
    macd_signal = "BUY" if macd_hist > 0 else "SELL"

    # Bollinger Band
    bb_upper = ind.get('BB.upper')
    bb_lower = ind.get('BB.lower')
    if bb_upper and bb_lower:
        bb_width = bb_upper - bb_lower
        bb_pos = ((price - bb_lower) / bb_width) * 100 if bb_width > 0 else 50
        if bb_pos > 80:
            bb_zone = "Overbought"
        elif bb_pos < 20:
            bb_zone = "Oversold"
        elif bb_pos > 60:
            bb_zone = "Upper"
        elif bb_pos < 40:
            bb_zone = "Lower"
        else:
            bb_zone = "Middle"
    else:
        bb_zone = "N/A"

    rec = analysis.summary.get('RECOMMENDATION', 'NEUTRAL')

    return {
        'price': price,
        'pct_from_high': pct_from_high,
        'rsi': rsi,
        'rsi_signal': rsi_signal,
        'macd_signal': macd_signal,
        'bb_zone': bb_zone,
        'recommendation': rec,
    }


def build_message():
    """Build the LINE notification message."""
    lines = ["\n📊 Weekly Stock Report"]
    lines.append("=" * 28)

    for symbol, (exchange, screener) in STOCKS.items():
        try:
            data = analyze_stock(symbol, exchange, screener)
            emoji = "🟢" if "BUY" in data['recommendation'] else "🔴" if "SELL" in data['recommendation'] else "🟡"
            lines.append(f"\n{emoji} {symbol} | ${data['price']:,.2f}")
            lines.append(f"   52W High: {data['pct_from_high']:+.1f}%")
            lines.append(f"   RSI({data['rsi']:.0f}): {data['rsi_signal']}")
            lines.append(f"   MACD: {data['macd_signal']}")
            lines.append(f"   BB: {data['bb_zone']}")
            lines.append(f"   Signal: {data['recommendation']}")
        except Exception as e:
            lines.append(f"\n⚠️ {symbol} | Error: {e}")

    lines.append("\n" + "=" * 28)
    lines.append("Source: TradingView + Yahoo Finance")
    return "\n".join(lines)


def send_line(message):
    """Send message via LINE Notify."""
    url = "https://notify-api.line.me/api/notify"
    headers = {"Authorization": f"Bearer {LINE_TOKEN}"}
    resp = requests.post(url, headers=headers, data={"message": message})
    print(f"LINE Status: {resp.status_code}")
    print(f"LINE Response: {resp.text}")
    resp.raise_for_status()


if __name__ == "__main__":
    msg = build_message()
    print(msg)
    send_line(msg)
    print("\n✅ Report sent successfully!")
