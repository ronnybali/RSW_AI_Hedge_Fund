from __future__ import annotations
import os
import requests
from datetime import datetime, timezone, timedelta
import yfinance as yf
import pandas as pd
from free_fund.config import load_config
from free_fund.orchestrator import CentralizedHedgeFundSystem

def send_telegram(message):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("ERROR: Telegram secrets not found!")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
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
    if symbol.endswith("=X") or symbol in ["GC=F", "GLD"]:
        return "FOREX & GOLD"
    return "ETF"

def get_tech_data(symbol):
    try:
        # Unduh data 1 bulan terakhir
        df = yf.download(symbol, period="1mo", interval="1d", progress=False)
        if df.empty:
            return None, None
        
        # Perbaiki format kolom jika multi-index (Yahoo Finance terkadang aneh)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        current_price = float(df['Close'].iloc[-1])
        
        # Hitung ATR 14
        df['H-L'] = df['High'] - df['Low']
        df['H-PC'] = abs(df['High'] - df['Close'].shift(1))
        df['L-PC'] = abs(df['Low'] - df['Close'].shift(1))
        df['TR'] = df[['H-L', 'H-PC', 'L-PC']].max(axis=1)
        atr = float(df['TR'].rolling(window=14).mean().iloc[-1])
        
        return current_price, atr
    except Exception as e:
        print(f"Data error for {symbol}: {e}")
        return None, None

def main():
    print("Memuat konfigurasi...")
    cfg = load_config("configs/rsw_config.yaml")
    system = CentralizedHedgeFundSystem(cfg)
    
    print("Menjalankan agen AI (1 siklus)...")
    decision = system.run_cycle(execute=False) 
    
    wita_time = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S WITA")
    
    # Kelompokkan aset
    groups = {"CRYPTO": [], "FOREX & GOLD": [], "ETF": []}
    for symbol, weight in decision.target_weights.items():
        if abs(weight) >= 0.02: # Hanya ambil bobot > 2%
            group_name = classify_symbol(symbol)
            groups[group_name].append((symbol, weight))
            
    pesan = "---------------------------------\n"
    pesan += "🤖 <b>RSW AI HEDGE FUND REPORT</b>\n"
    pesan += "---------------------------------\n"
    pesan += f"🕒 {wita_time}\n\n"
    
    for group_name, assets in groups.items():
        if not assets: continue
        
        # Urutkan berdasarkan bobot terbesar
        assets.sort(key=lambda x: abs(x[1]), reverse=True)
        top_assets = assets[:3] # Ambil Top 3 tiap kategori
        
        pesan += f"<b>📌 {group_name}</b>\n"
        
        for symbol, weight in top_assets:
            name = clean_ticker_name(symbol)
            is_long = weight > 0
            
            # Ambil harga dan ATR
            price, atr = get_tech_data(symbol)
            
            if price is None or atr is None:
                # Jika gagal ambil data, tampilkan bobot saja
                emoji = "🟢" if is_long else "🔴"
                pesan += f"{emoji} <b>{name}</b> | Bobot: {abs(weight)*100:.1f}%\n"
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
                
            pesan += f"{emoji} <b>{name}</b> [{aksi} - {abs(weight)*100:.1f}%]\n"
            pesan += f"├ Entry: <code>{price:.4f}</code>\n"
            pesan += f"├ SL: <code>{sl:.4f}</code>\n"
            pesan += f"└ TP: <code>{tp:.4f}</code>\n\n"
            
    pesan += "---------------------------------\n"
    pesan += "<i>*Hanya menampilkan Top 3 per kategori</i>"
    
    print(pesan)
    send_telegram(pesan)
    print("Selesai!")

if __name__ == "__main__":
    main()
