from __future__ import annotations
import os
import sys
import warnings
import requests
import pandas as pd
import numpy as np
import yfinance as yf
import json
from datetime import datetime, timezone, timedelta
from free_fund.config import load_config
from free_fund.orchestrator import CentralizedHedgeFundSystem

warnings.filterwarnings("ignore")
sys.stdout.reconfigure(line_buffering=True)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID_VPS = os.getenv("TELEGRAM_CHAT_ID_VPS")

def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    for i in range(0, len(message), 4000):
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID_VPS, "text": message[i:i+4000], "parse_mode": "HTML"}, timeout=15)

def clean_symbol_name(symbol):
    if symbol == 'GC=F': return 'XAUUSD (Gold)'
    if symbol.endswith('=X'): return symbol.replace('=X', '')
    return symbol

def atr(df, period=14):
    tr = pd.concat([df["High"] - df["Low"], (df["High"] - df["Close"].shift()).abs(), (df["Low"] - df["Close"].shift()).abs()], axis=1).max(axis=1)
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
    
    # FILTER: HANYA FOREX & GOLD
    forex_gold_assets = [k for k in weights.keys() if k.endswith("=X") or k == "GC=F"]
    top_assets = {k: weights[k] for k in forex_gold_assets if abs(weights[k]) >= 0.02}
    
    orders = []
    print(f"Menganalisis {len(top_assets)} aset Forex & Gold...")
    
    for symbol, weight in top_assets.items():
        tech = get_tech_data(symbol)
        if not tech: continue
        
        is_long = weight > 0
        price, a, tech_sig = tech["price"], tech["atr"], tech["signal"]
        
        # LOGIKA FUSION
        if is_long and tech_sig == "BULLISH":
            orders.append({"symbol": symbol, "type": "BUY MARKET", "price": price, "weight": weight})
        elif not is_long and tech_sig == "BEARISH":
            orders.append({"symbol": symbol, "type": "SELL MARKET", "price": price, "weight": weight})

    # SIMPAN DAILY BIAS UNTUK VPS
    daily_bias = {}
    for o in orders:
        arah = "BUY" if "BUY" in o['type'] else "SELL"
        daily_bias[o['symbol']] = arah
        
    with open("daily_bias.json", "w") as f:
        json.dump(daily_bias, f, indent=4)
    print("✅ File daily_bias.json berhasil disimpan!")

    # BANGUN LAPORAN TELEGRAM
    wita_time = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M WITA")
    msg = "-------------------------------------------\n"
    msg += "🔥 <b>FUSION MACRO REPORT (FOREX & GOLD)</b>\n"
    msg += f"<b>{wita_time}</b>\n"
    msg += "-------------------------------------------\n\n"
    
    if not orders:
        msg += "⚠️ <b>TIDAK ADA SINKRONISASI MAKRO-MIKRO</b>\n"
    else:
        msg += "🎯 <b>ARAHAN HARI INI (VPS STANDBY)</b>\n\n"
        for o in orders:
            name = clean_symbol_name(o['symbol'])
            emoji = "🟢" if "BUY" in o['type'] else "🔴"
            msg += f"{emoji} <b>{name}</b> | <b>{o['type']}</b>\n"
            msg += f"<i>(Bobot AI: {abs(o['weight'])*100:.1f}%)</i>\n\n"
                
    msg += "-------------------------------------------\n"
    msg += "<i>File daily_bias.json telah diperbarui untuk VPS.</i>"
    
    print(msg)
    send_telegram(msg)

if __name__ == "__main__":
    main()
