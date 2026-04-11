#!/usr/bin/env python3
"""Weekly Stock Technical Analysis Report - LINE Messaging API via GitHub Actions"""

import os
import time
import requests
from tradingview_ta import TA_Handler, Interval
import yfinance as yf

LINE_CHANNEL_TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
LINE_USER_ID = os.environ["LINE_USER_ID"]

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
    """Get price data from Yahoo Finance."""
    ticker = yf.Ticker(symbol)
    info = ticker.info
    price = info.get('regularMarketPrice') or info.get('currentPrice')
    high_52w = info.get('fiftyTwoWeekHigh')
    low_52w = info.get('fiftyTwoWeekLow')
    prev_close = info.get('previousClose') or info.get('regularMarketPreviousClose')
    market_cap = info.get('marketCap')
    return {
        'price': price,
        '52w_high': high_52w,
        '52w_low': low_52w,
        'prev_close': prev_close,
        'market_cap': market_cap,
    }


def format_market_cap(cap):
    """Format market cap to readable string."""
    if not cap:
        return "N/A"
    if cap >= 1e12:
        return f"${cap/1e12:.2f}T"
    if cap >= 1e9:
        return f"${cap/1e9:.1f}B"
    return f"${cap/1e6:.0f}M"


def analyze_stock(symbol, exchange, screener):
    """Analyze a single stock and return detailed message."""
    yf_data = get_yahoo_price(symbol)
    handler = TA_Handler(
        symbol=symbol, exchange=exchange,
        screener=screener, interval=Interval.INTERVAL_1_DAY
    )
    analysis = handler.get_analysis()
    ind = analysis.indicators
    summary = analysis.summary

    price = yf_data['price']
    high_52w = yf_data['52w_high']
    low_52w = yf_data['52w_low']
    prev_close = yf_data['prev_close']
    market_cap = yf_data['market_cap']

    pct_from_high = ((price - high_52w) / high_52w) * 100 if price and high_52w else 0
    pct_from_low = ((price - low_52w) / low_52w) * 100 if price and low_52w else 0
    day_change = ((price - prev_close) / prev_close) * 100 if price and prev_close else 0

    # RSI
    rsi = ind.get('RSI')
    if rsi and rsi > 70:
        rsi_signal = "⚠️ OVERBOUGHT (SELL)"
    elif rsi and rsi < 30:
        rsi_signal = "✅ OVERSOLD (BUY)"
    elif rsi and rsi > 55:
        rsi_signal = "Bullish"
    elif rsi and rsi < 45:
        rsi_signal = "Bearish"
    else:
        rsi_signal = "Neutral"

    # MACD
    macd_val = ind.get('MACD.macd', 0) or 0
    macd_sig = ind.get('MACD.signal', 0) or 0
    macd_hist = macd_val - macd_sig
    if macd_hist > 0 and macd_val > 0:
        macd_signal = "✅ STRONG BUY"
    elif macd_hist > 0:
        macd_signal = "Bullish Crossover"
    elif macd_hist < 0 and macd_val < 0:
        macd_signal = "⚠️ STRONG SELL"
    else:
        macd_signal = "Bearish Crossover"

    # Bollinger Band
    bb_upper = ind.get('BB.upper')
    bb_middle = ind.get('BB.middle')
    bb_lower = ind.get('BB.lower')
    if bb_upper and bb_lower:
        bb_width = bb_upper - bb_lower
        bb_pos = ((price - bb_lower) / bb_width) * 100 if bb_width > 0 else 50
        if bb_pos > 80:
            bb_zone = "⚠️ Upper Band (Overbought)"
        elif bb_pos < 20:
            bb_zone = "✅ Lower Band (Oversold)"
        elif bb_pos > 60:
            bb_zone = "Above Middle (Bullish)"
        elif bb_pos < 40:
            bb_zone = "Below Middle (Bearish)"
        else:
            bb_zone = "Middle Band (Neutral)"
    else:
        bb_upper = bb_middle = bb_lower = 0
        bb_pos = 50
        bb_zone = "N/A"

    # SMA / EMA
    sma20 = ind.get('SMA20')
    sma50 = ind.get('SMA50')
    sma200 = ind.get('SMA200')
    ema20 = ind.get('EMA20')

    # Moving Average signals
    ma_signals = []
    if price and sma50 and sma200:
        if sma50 > sma200:
            ma_signals.append("Golden Cross (SMA50>200)")
        else:
            ma_signals.append("Death Cross (SMA50<200)")
    if price and sma20:
        if price > sma20:
            ma_signals.append("Price > SMA20")
        else:
            ma_signals.append("Price < SMA20")

    # Candlestick patterns
    patterns_found = []
    pattern_map = {
        'Rec.CDL.ENGULFING': 'Engulfing',
        'Rec.CDL.DOJI': 'Doji',
        'Rec.CDL.HAMMER': 'Hammer',
        'Rec.CDL.MORNINGSTAR': 'Morning Star',
        'Rec.CDL.EVENINGSTAR': 'Evening Star',
        'Rec.CDL.HARAMI': 'Harami',
        'Rec.CDL.SPINNINGTOP': 'Spinning Top',
        'Rec.CDL.MARUBOZU': 'Marubozu',
        'Rec.CDL.3WHITESOLDIERS': '3 White Soldiers',
        'Rec.CDL.3BLACKCROWS': '3 Black Crows',
    }
    for key, name in pattern_map.items():
        val = ind.get(key)
        if val and val != 0:
            direction = "🟢Bullish" if val > 0 else "🔴Bearish"
            patterns_found.append(f"{name} ({direction})")

    # Overall signal
    rec = summary.get('RECOMMENDATION', 'NEUTRAL')
    buy_count = summary.get('BUY', 0)
    sell_count = summary.get('SELL', 0)
    neutral_count = summary.get('NEUTRAL', 0)

    if 'STRONG_BUY' in rec:
        overall_emoji = "🟢🟢"
        verdict = "STRONG BUY — เข้าซื้อได้"
    elif 'BUY' in rec:
        overall_emoji = "🟢"
        verdict = "BUY — สัญญาณซื้อ แต่ควรดู entry point"
    elif 'STRONG_SELL' in rec:
        overall_emoji = "🔴🔴"
        verdict = "STRONG SELL — หลีกเลี่ยง"
    elif 'SELL' in rec:
        overall_emoji = "🔴"
        verdict = "SELL — ยังไม่ควรเข้า รอสัญญาณกลับตัว"
    else:
        overall_emoji = "🟡"
        verdict = "NEUTRAL — รอจังหวะ ยังไม่มีสัญญาณชัด"

    # Build message
    lines = [
        f"{'='*30}",
        f"{overall_emoji} {symbol} ({exchange})",
        f"{'='*30}",
        f"",
        f"💰 ราคา & Market Cap",
        f"   Price: ${price:,.2f} ({day_change:+.2f}%)",
        f"   Market Cap: {format_market_cap(market_cap)}",
        f"   52W High: ${high_52w:,.2f} ({pct_from_high:+.1f}%)",
        f"   52W Low: ${low_52w:,.2f} ({pct_from_low:+.1f}%)",
        f"",
        f"📊 RSI (14): {rsi:.1f}" if rsi else "📊 RSI: N/A",
        f"   Signal: {rsi_signal}",
        f"",
        f"📈 MACD",
        f"   Line: {macd_val:.4f}",
        f"   Signal: {macd_sig:.4f}",
        f"   Histogram: {macd_hist:+.4f}",
        f"   Signal: {macd_signal}",
        f"",
        f"🎯 Bollinger Band",
        f"   Upper: ${bb_upper:,.2f}" if bb_upper else "   Upper: N/A",
        f"   Middle: ${bb_middle:,.2f}" if bb_middle else "   Middle: N/A",
        f"   Lower: ${bb_lower:,.2f}" if bb_lower else "   Lower: N/A",
        f"   Position: {bb_pos:.0f}%",
        f"   Zone: {bb_zone}",
        f"",
        f"📐 Moving Averages",
        f"   SMA20: ${sma20:,.2f}" if sma20 else "   SMA20: N/A",
        f"   SMA50: ${sma50:,.2f}" if sma50 else "   SMA50: N/A",
        f"   SMA200: ${sma200:,.2f}" if sma200 else "   SMA200: N/A",
        f"   EMA20: ${ema20:,.2f}" if ema20 else "   EMA20: N/A",
    ]
    if ma_signals:
        lines.append(f"   Signals: {', '.join(ma_signals)}")

    lines.append(f"")
    lines.append(f"🕯 Candlestick Patterns (Daily)")
    if patterns_found:
        for p in patterns_found:
            lines.append(f"   • {p}")
    else:
        lines.append(f"   ไม่พบ pattern สำคัญ")

    lines.extend([
        f"",
        f"{'─'*30}",
        f"📋 สรุป: {rec}",
        f"   (Buy:{buy_count} | Sell:{sell_count} | Neutral:{neutral_count})",
        f"",
        f"💡 {verdict}",
        f"{'='*30}",
    ])

    return "\n".join(lines)


def send_line(message):
    """Send a single message via LINE Messaging API."""
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Authorization": f"Bearer {LINE_CHANNEL_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "to": LINE_USER_ID,
        "messages": [{"type": "text", "text": message}],
    }
    resp = requests.post(url, headers=headers, json=payload)
    if resp.status_code != 200:
        print(f"  LINE Error: {resp.status_code} {resp.text}")
    return resp.status_code


def main():
    # Send header message
    header = "📊 Weekly Stock Technical Analysis\n" + "=" * 30 + "\nวิเคราะห์หุ้น 8 ตัว ณ วันนี้\n\nหุ้น: GOOGL | TSLA | BABA | NFLX | NVDA | META | MSFT | IREN\n\nรายละเอียดแต่ละตัวจะส่งตามมาครับ 👇"
    send_line(header)
    time.sleep(1)

    success = 0
    for symbol, (exchange, screener) in STOCKS.items():
        try:
            print(f"Analyzing {symbol}...")
            msg = analyze_stock(symbol, exchange, screener)
            print(msg)
            status = send_line(msg)
            if status == 200:
                success += 1
                print(f"  ✅ Sent {symbol}")
            time.sleep(1)  # Rate limit
        except Exception as e:
            print(f"  ❌ {symbol} Error: {e}")
            send_line(f"⚠️ {symbol} — Error: {e}")
            time.sleep(1)

    # Send footer
    footer = f"✅ Weekly Report Complete\n\n{success}/{len(STOCKS)} หุ้นวิเคราะห์สำเร็จ\n\nSource: TradingView + Yahoo Finance\n⚠️ ข้อมูลนี้ไม่ใช่คำแนะนำในการลงทุน"
    send_line(footer)
    print(f"\n🎉 Done! Sent {success}/{len(STOCKS)} stocks")


if __name__ == "__main__":
    main()
