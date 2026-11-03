from __future__ import annotations
import os
import sys
import warnings
import requests
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timezone, timedelta
from free_fund.config import load_config
from free_fund.orchestrator import CentralizedHedgeFundSystem

warnings.filterwarnings("ignore")
sys.stdout.reconfigure(line_buffering=True)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram secrets missing!")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]
    for chunk in chunks:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": chunk, "parse_mode": "HTML"}, timeout=15)

# FUNGSI BARU UNTUK MERAPIKAN NAMA ASET
def clean_symbol_name(symbol):
    if symbol == 'GC=F': return 'XAUUSD (Gold)'
    if symbol.endswith('-USD'): return symbol.replace('-USD', '')
    if symbol.endswith('=X'): return symbol.replace('=X', '')
    return symbol

def atr(df, period=14):
    high, low, close = df["High"], df["Low"], df["Close"]
    tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
    return float(tr.rolling(period).mean().iloc[-1])

def fisher_transform(df, period=9):
    high, low = df["High"], df["Low"]
    price = (high + low) / 2
    min_low, max_high = low.rolling(period).min(), high.rolling(period).max()
    rng = (max_high - min_low).replace(0, np.nan)
    x = 2 * ((price - min_low) / rng - 0.5)
    x = x.clip(-0.999, 0.999)
    val = 0.33 * 2 * x + 0.67 * x.shift(1).fillna(0)
    val = val.clip(-0.999, 0.999)
    return (0.5 * np.log((1 + val) / (1 - val))).rolling(2).mean()

def analyze_tf(df):
    if df is None or len(df) < 60: return None
    close = df["Close"]
    price, ma50 = float(close.iloc[-1]), float(close.rolling(50).mean().iloc[-1])
    fish = fisher_transform(df).dropna()
    if len(fish) < 2: return None
    f_now = float(fish.iloc[-1])
    
    trend = "Bullish" if price > ma50 else "Bearish"
    sig = "BULLISH" if (f_now > 0 and trend == "Bullish") else ("BEARISH" if (f_now < 0 and trend == "Bearish") else "NEUTRAL")
    return {"fisher": f_now, "trend": trend, "signal": sig}

def get_tech_data(symbol):
    try:
        df = yf.download(symbol, period="6mo", interval="1d", progress=False, auto_adjust=True, timeout=5)
        if df is None or df.empty: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        
        tf = analyze_tf(df)
        if not tf: return None
        
        price = float(df["Close"].iloc[-1])
        a = atr(df)
        return {"price": price, "atr": a, "signal": tf["signal"]}
    except Exception:
        return None

def main():
    print("Memuat konfigurasi Hedge Fund...")
    cfg = load_config("configs/rsw_config.yaml")
    system = CentralizedHedgeFundSystem(cfg)
    
    print("Menjalankan Agen Hedge Fund...")
    decision = system.run_cycle(execute=False)
    weights = decision.target_weights
    
    # Filter aset yang alokasinya > 2%
    top_assets = {k: v for k, v in weights.items() if abs(v) >= 0.02}
    
    golden_buys, golden_sells = [], []
    
    print(f"Menganalisis {len(top_assets)} aset kandidat dengan logika Swing Trader...")
    for symbol, weight in top_assets.items():
        tech = get_tech_data(symbol)
        if not tech: continue
        
        is_long = weight > 0
        price, a, tech_sig = tech["price"], tech["atr"], tech["signal"]
        
        # LOGIKA FUSION (Penyaringan Keras)
        if is_long and tech_sig == "BULLISH":
            # Sinyal Emas BUY
            sl, tp = price - 1.5 * a, price + 3.0 * a
            golden_buys.append({"symbol": symbol, "price": price, "sl": sl, "tp": tp, "weight": weight})
            
        elif not is_long and tech_sig == "BEARISH":
            # Sinyal Emas SELL
            sl, tp = price + 1.5 * a, price - 3.0 * a
            golden_sells.append({"symbol": symbol, "price": price, "sl": sl, "tp": tp, "weight": weight})

    # Bangun Pesan Telegram
    wita_time = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M WITA")
    msg = "-------------------------------------------\n"
    msg += "🔥 <b>FUSION HIGH-PROBABILITY REPORT</b>\n"
    msg += f"<b>{wita_time}</b>\n"
    msg += "-------------------------------------------\n\n"
    
    if not golden_buys and not golden_sells:
        msg += "⚠️ <b>TIDAK ADA SINYAL EMAS HARI INI</b>\n"
        msg += "<i>Hedge Fund dan Swing Trader tidak menemukan titik temu. Pasar sedang tidak sinkron. Tetap Cash.</i>\n"
    else:
        if golden_buys:
            msg += "🟢 <b>GOLDEN BUY SIGNALS</b>\n"
            msg += "(Hedge Fund & Teknikal Sepakat NAIK)\n\n"
            for b in golden_buys:
                name = clean_symbol_name(b['symbol']) # MENGGUNAKAN FUNGSI BARU
                msg += f"🚀 <b>{name}</b> [<b>BUY</b>]\n"
                msg += f"├ Entry: {b['price']:.5g}\n"
                msg += f"├ SL: {b['sl']:.5g}\n"
                msg += f"└ TP: {b['tp']:.5g}\n"
                msg += f"<i>Alokasi Hedge Fund: {abs(b['weight'])*100:.1f}%</i>\n\n"
                
        if golden_sells:
            msg += "🔴 <b>GOLDEN SELL SIGNALS</b>\n"
            msg += "(Hedge Fund & Teknikal Sepakat TURUN)\n\n"
            for s in golden_sells:
                name = clean_symbol_name(s['symbol']) # MENGGUNAKAN FUNGSI BARU
                msg += f"🩸 <b>{name}</b> [<b>SELL</b>]\n"
                msg += f"├ Entry: {s['price']:.5g}\n"
                msg += f"├ SL: {s['sl']:.5g}\n"
                msg += f"└ TP: {s['tp']:.5g}\n"
                msg += f"<i>Alokasi Hedge Fund: {abs(s['weight'])*100:.1f}%</i>\n\n"
                
    msg += "-------------------------------------------\n"
    msg += "<i>Sistem ini hanya menampilkan aset yang searah antara Makro & Mikro.</i>"
    
    print(msg)
    send_telegram(msg)

if __name__ == "__main__":
    main()
