from __future__ import annotations
import os
import json
import requests
from datetime import datetime, timezone, timedelta
from free_fund.config import load_config
from free_fund.orchestrator import CentralizedHedgeFundSystem

def send_telegram(message):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("Telegram secrets not found.")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Failed to send Telegram: {e}")

def main():
    print("Memuat konfigurasi...")
    cfg = load_config("configs/rsw_config.yaml")
    system = CentralizedHedgeFundSystem(cfg)
    
    print("Menjalankan agen AI (1 siklus)...")
    # execute=False artinya HANYA menghitung, TIDAK order ke broker
    decision = system.run_cycle(execute=False) 
    
    # Waktu WITA (UTC+8)
    wita_time = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S WITA")
    
    # Susun pesan
    pesan = "---------------------------------\n"
    pesan += "🤖 *RSW AI HEDGE FUND REPORT*\n"
    pesan += "---------------------------------\n"
    pesan += f"🕒 {wita_time}\n\n"
    pesan += "*Alokasi Portofolio:*\n"
    
    # Urutkan dari bobot terbesar
    sorted_weights = sorted(decision.target_weights.items(), key=lambda x: abs(x[1]), reverse=True)
    
    ada_aset = False
    for symbol, weight in sorted_weights:
        if abs(weight) > 0.01: # Hanya tampilkan jika bobot > 1%
            emoji = "🟢" if weight > 0 else "🔴"
            pesan += f"{emoji} `{symbol}`: {weight*100:.1f}%\n"
            ada_aset = True
            
    if not ada_aset:
        pesan += "_Semua aset dalam status Cash (0%)_\n"
        
    pesan += "\n*Status Risiko:*\n"
    if decision.risk_flags:
        pesan += f"⚠️ {', '.join(decision.risk_flags)}\n"
    else:
        pesan += "✅ Normal\n"
        
    pesan += "---------------------------------\n"
    pesan += "_Laporan dari AI Native Hedge Fund_"
    
    print(pesan)
    send_telegram(pesan)
    print("Selesai!")

if __name__ == "__main__":
    main()
