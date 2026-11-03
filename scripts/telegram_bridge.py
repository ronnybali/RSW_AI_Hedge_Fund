from __future__ import annotations
import os
import requests
from datetime import datetime, timezone, timedelta
import yfinance as yf
import pandas as pd
import numpy as np
from free_fund.config import load_config
from free_fund.orchestrator import CentralizedHedgeFundSystem

def send_telegram(message):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("ERROR: Telegram secrets not found!")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    # Menggunakan HTML untuk format Bold
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
    try:
        response = requests.post(url, json=payload, timeout=10)
        print(f"Telegram API Response: {response.status_code}")
    except Exception as e:
        print(f"Failed to send Telegram: {e}")

def clean_ticker_name(symbol):
    if symbol == "GC=F": return "XAUUSD (Gold)"
    if symbol.endswith("-USD"): return symbol.replace("-USD", "")
    if symbol.endswith("=X"): return symbol.replace("=X", "")
    return symbol

def classify_symbol(symbol):
    if symbol.endswith("-USD"):
        return "CRYPTO"
    if symbol.endswith("=X") or symbol == "GC=F":
        return "FOREX & GOLD"
    return "ETF"

def get_tech_data(symbol):
    try:
        df = yf.download(symbol, period="6mo", interval="1d", progress=False)
        if df.empty:
            return None, None, None, None
            
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        close = df['Close']
        high = df['High']
        low = df['Low']
        
        current_price = float(close.iloc[-1])
        
        tr = pd.concat([high - low, abs(high - close.shift()), abs(low - close.shift())], axis=1).max(axis=1)
        atr = float(tr.rolling(14).mean().iloc[-1])
        
        ma50 = float(close.rolling(50).mean().iloc[-1])
        
        hl2 = (high + low) / 2
        min_low = low.rolling(9).min()
        max_high = high.rolling(9).max()
        val = 2 * ((hl2 - min_low) / (max_high - min_low) - 0.5)
        val = val.ewm(span=5, adjust=False).mean()
        val = val.clip(-0.999, 0.999)
        fisher = 0.5 * np.log((1 + val) / (1 - val))
        current_fisher = float(fisher.iloc[-1])
        
        return current_price, atr, ma50, current_fisher
    except Exception as e:
        print(f"Data error for {symbol}: {e}")
        return None, None, None, None

def calculate_confidence(weight, is_long, price, ma50, fisher):
    conf = 50 
    weight_abs = abs(weight)
    if weight_abs >= 0.10: conf += 25
    elif weight_abs >= 0.05: conf += 15
    else: conf += 5
    
    if is_long:
        if fisher > 0: conf += 10
        if price > ma50: conf += 10
    else:
        if fisher < 0: conf += 10
        if price < ma50: conf += 10
        
    conf = min(99, conf) 
    
    if conf >= 75: status = "KUAT"
    elif conf >= 60: status = "SEDANG"
    else: status = "LEMAH"
    
    return conf, status

def main():
    print("Memuat konfigurasi...")
    cfg = load_config("configs/rsw_config.yaml")
    system = CentralizedHedgeFundSystem(cfg)
    
    print("Menjalankan agen AI (1 siklus)...")
    decision = system.run_cycle(execute=False) 
    
    wita_time = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8))).strftime("%Y-%m-%d  %H:%M WITA")
    
    groups = {"CRYPTO": [], "FOREX & GOLD": [], "ETF": []}
    for symbol, weight in decision.target_weights.items():
        if abs(weight) >= 0.0: 
            group_name = classify_symbol(symbol)
            groups[group_name].append((symbol, weight))
            
    # 1 & 2: Header Utama di-Bold
    pesan = "-------------------------------------------\n"
    pesan += "<b>RSW AI HEDGE FUND REPORT</b>\n"
    pesan += f"<b>{wita_time}</b>\n"
    pesan += "-------------------------------------------\n\n"
    
    for group_name, assets in groups.items():
        if not assets: continue
        
        assets.sort(key=lambda x: abs(x[1]), reverse=True)
        
        # 3, 4, 5: Nama Kategori di-Bold
        pesan += "-------------------------\n"
        pesan += f"<b>{group_name}</b>\n"
        pesan += "-------------------------\n\n"
        
        for symbol, weight in assets:
            name = clean_ticker_name(symbol)
            
            if abs(weight) < 0.01:
                pesan += f"⚪ <b>{name}</b> [NETRAL]\n\n"
                continue
                
            is_long = weight > 0
            price, atr, ma50, fisher = get_tech_data(symbol)
            
            if price is None or atr is None:
                emoji = "🟢" if is_long else "🔴"
                aksi = "BUY" if is_long else "SELL"
                # 6: Menghapus persentase dari dalam kurung siku
                pesan += f"{emoji} <b>{name}</b> [{aksi}]\n"
                pesan += "(Gagal mengambil data teknikal)\n\n"
                continue
                
            if is_long:
                sl = price - (1.5 * atr)
                tp = price + (3.0 * atr)
                emoji = "🟢"
                aksi = "BUY"
            else:
                sl = price + (1.5 * atr)
                tp = price - (3.0 * atr)
                emoji = "🔴"
                aksi = "SELL"
                
            conf, status = calculate_confidence(weight, is_long, price, ma50, fisher)
            
            # 6: Menghapus persentase dari dalam kurung siku
            pesan += f"{emoji} <b>{name}</b> [{aksi}]\n"
            pesan += f"├ Entry: <code>{price:.4f}</code>\n"
            pesan += f"├ SL: <code>{sl:.4f}</code>\n"
            pesan += f"└ TP: <code>{tp:.4f}</code>\n"
            pesan += f"Confidence: {conf}% ({status})\n\n"
            
    print(pesan)
    send_telegram(pesan)
    print("Selesai!")

if __name__ == "__main__":
    main()
