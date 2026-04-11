#!/usr/bin/env python3
"""Weekly Stock Technical Analysis Report - LINE Messaging API via GitHub Actions"""

import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from tradingview_ta import TA_Handler, Interval
import yfinance as yf

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

CANDLE_PATTERNS = {
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


def get_config():
    """Validate and return required config from environment."""
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    user_id = os.environ.get("LINE_USER_ID")
    if not token or not user_id:
        print("ERROR: Missing required environment variables:")
        if not token:
            print("  - LINE_CHANNEL_ACCESS_TOKEN")
        if not user_id:
            print("  - LINE_USER_ID")
        sys.exit(1)
    return token, user_id


def get_yahoo_price(symbol):
    """Get price data from Yahoo Finance."""
    ticker = yf.Ticker(symbol)
    info = ticker.info
    return {
        'price': info.get('regularMarketPrice') or info.get('currentPrice'),
        '52w_high': info.get('fiftyTwoWeekHigh'),
        '52w_low': info.get('fiftyTwoWeekLow'),
        'prev_close': info.get('previousClose') or info.get('regularMarketPreviousClose'),
        'market_cap': info.get('marketCap'),
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


def safe_price_fmt(value):
    """Safely format a price value."""
    if value is None:
        return "N/A"
    return f"${value:,.2f}"


def safe_pct_fmt(value):
    """Safely format a percentage value."""
    if value is None:
        return "N/A"
    return f"{value:+.1f}%"


def fetch_stock_data(symbol, exchange, screener):
    """Fetch all data for a single stock (yfinance + TradingView)."""
    yf_data = get_yahoo_price(symbol)
    handler = TA_Handler(
        symbol=symbol, exchange=exchange,
        screener=screener, interval=Interval.INTERVAL_1_DAY
    )
    analysis = handler.get_analysis()
    return symbol, yf_data, analysis


def analyze_stock(symbol, exchange, yf_data, analysis):
    """Analyze a single stock and return detailed message."""
    ind = analysis.indicators
    summary = analysis.summary

    price = yf_data['price']
    high_52w = yf_data['52w_high']
    low_52w = yf_data['52w_low']
    prev_close = yf_data['prev_close']
    market_cap = yf_data['market_cap']

    pct_from_high = ((price - high_52w) / high_52w) * 100 if price and high_52w else None
    pct_from_low = ((price - low_52w) / low_52w) * 100 if price and low_52w else None
    day_change = ((price - prev_close) / prev_close) * 100 if price and prev_close else None

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
        bb_pos = ((price - bb_lower) / bb_width) * 100 if price and bb_width > 0 else 50
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
        bb_middle = None
        bb_pos = None
        bb_zone = "N/A"

    # SMA / EMA
    sma20 = ind.get('SMA20')
    sma50 = ind.get('SMA50')
    sma200 = ind.get('SMA200')
    ema20 = ind.get('EMA20')

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
    for key, name in CANDLE_PATTERNS.items():
        val = ind.get(key)
        if val and val != 0:
            direction = "🟢Bullish" if val > 0 else "🔴Bearish"
            patterns_found.append(f"{name} ({direction})")

    # Overall signal
    rec = summary.get('RECOMMENDATION', 'NEUTRAL')
    buy_count = summary.get('BUY', 0)
    sell_count = summary.get('SELL', 0)
    neutral_count = summary.get('NEUTRAL', 0)

    if rec == 'STRONG_BUY':
        overall_emoji = "🟢🟢"
        verdict = "STRONG BUY — เข้าซื้อได้"
    elif rec == 'BUY':
        overall_emoji = "🟢"
        verdict = "BUY — สัญญาณซื้อ แต่ควรดู entry point"
    elif rec == 'STRONG_SELL':
        overall_emoji = "🔴🔴"
        verdict = "STRONG SELL — หลีกเลี่ยง"
    elif rec == 'SELL':
        overall_emoji = "🔴"
        verdict = "SELL — ยังไม่ควรเข้า รอสัญญาณกลับตัว"
    else:
        overall_emoji = "🟡"
        verdict = "NEUTRAL — รอจังหวะ ยังไม่มีสัญญาณชัด"

    # Build message
    lines = [
        "=" * 30,
        f"{overall_emoji} {symbol} ({exchange})",
        "=" * 30,
        "",
        "💰 ราคา & Market Cap",
        f"   Price: {safe_price_fmt(price)} ({safe_pct_fmt(day_change)})",
        f"   Market Cap: {format_market_cap(market_cap)}",
        f"   52W High: {safe_price_fmt(high_52w)} ({safe_pct_fmt(pct_from_high)})",
        f"   52W Low: {safe_price_fmt(low_52w)} ({safe_pct_fmt(pct_from_low)})",
        "",
        f"📊 RSI (14): {rsi:.1f}" if rsi else "📊 RSI: N/A",
        f"   Signal: {rsi_signal}",
        "",
        "📈 MACD",
        f"   Line: {macd_val:.4f}",
        f"   Signal: {macd_sig:.4f}",
        f"   Histogram: {macd_hist:+.4f}",
        f"   Signal: {macd_signal}",
        "",
        "🎯 Bollinger Band",
        f"   Upper: {safe_price_fmt(bb_upper)}",
        f"   Middle: {safe_price_fmt(bb_middle)}",
        f"   Lower: {safe_price_fmt(bb_lower)}",
        f"   Position: {bb_pos:.0f}%" if bb_pos is not None else "   Position: N/A",
        f"   Zone: {bb_zone}",
        "",
        "📐 Moving Averages",
        f"   SMA20: {safe_price_fmt(sma20)}",
        f"   SMA50: {safe_price_fmt(sma50)}",
        f"   SMA200: {safe_price_fmt(sma200)}",
        f"   EMA20: {safe_price_fmt(ema20)}",
    ]
    if ma_signals:
        lines.append(f"   Signals: {', '.join(ma_signals)}")

    lines.append("")
    lines.append("🕯 Candlestick Patterns (Daily)")
    if patterns_found:
        for p in patterns_found:
            lines.append(f"   • {p}")
    else:
        lines.append("   ไม่พบ pattern สำคัญ")

    lines.extend([
        "",
        "─" * 30,
        f"📋 สรุป: {rec}",
        f"   (Buy:{buy_count} | Sell:{sell_count} | Neutral:{neutral_count})",
        "",
        f"💡 {verdict}",
        "=" * 30,
    ])

    return "\n".join(lines)


def send_line(message, session, token, user_id):
    """Send a single message via LINE Messaging API."""
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "to": user_id,
        "messages": [{"type": "text", "text": message}],
    }
    resp = session.post(url, headers=headers, json=payload, timeout=15)
    if resp.status_code != 200:
        print(f"  LINE Error: {resp.status_code} {resp.text}")
    return resp.status_code


def main():
    token, user_id = get_config()
    session = requests.Session()

    # Send header
    header = (
        "📊 Weekly Stock Technical Analysis\n"
        + "=" * 30
        + "\nวิเคราะห์หุ้น 8 ตัว ณ วันนี้\n\n"
        "หุ้น: GOOGL | TSLA | BABA | NFLX | NVDA | META | MSFT | IREN\n\n"
        "รายละเอียดแต่ละตัวจะส่งตามมาครับ 👇"
    )
    send_line(header, session, token, user_id)
    time.sleep(1)

    # Fetch all stock data in parallel
    print("Fetching stock data in parallel...")
    stock_data = {}
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(fetch_stock_data, symbol, exchange, screener): symbol
            for symbol, (exchange, screener) in STOCKS.items()
        }
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                sym, yf_data, analysis = future.result()
                stock_data[sym] = (yf_data, analysis)
                print(f"  ✅ Fetched {sym}")
            except Exception as e:
                stock_data[symbol] = None
                print(f"  ❌ Failed {symbol}: {e}")

    # Send messages sequentially (LINE rate limit)
    success = 0
    for symbol, (exchange, _screener) in STOCKS.items():
        data = stock_data.get(symbol)
        if data is None:
            try:
                send_line(f"⚠️ {symbol} — ไม่สามารถวิเคราะห์ได้", session, token, user_id)
            except Exception:
                pass
        else:
            try:
                yf_data, analysis = data
                msg = analyze_stock(symbol, exchange, yf_data, analysis)
                print(msg)
                status = send_line(msg, session, token, user_id)
                if status == 200:
                    success += 1
                    print(f"  ✅ Sent {symbol}")
            except Exception as e:
                print(f"  ❌ {symbol} Error: {e}")
                try:
                    send_line(f"⚠️ {symbol} — ไม่สามารถวิเคราะห์ได้", session, token, user_id)
                except Exception:
                    pass
        time.sleep(1)

    # Send footer
    footer = (
        f"✅ Weekly Report Complete\n\n"
        f"{success}/{len(STOCKS)} หุ้นวิเคราะห์สำเร็จ\n\n"
        "Source: TradingView + Yahoo Finance\n"
        "⚠️ ข้อมูลนี้ไม่ใช่คำแนะนำในการลงทุน"
    )
    send_line(footer, session, token, user_id)
    print(f"\n🎉 Done! Sent {success}/{len(STOCKS)} stocks")


if __name__ == "__main__":
    main()
