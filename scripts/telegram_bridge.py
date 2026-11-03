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
        print("ERROR: Telegram secrets not found in environment!")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    # Ubah parse_mode ke HTML
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
    try:
        response = requests.post(url, json=payload, timeout=10)
        print(f"Telegram API Response: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Failed to send Telegram: {e}")

def main():
    print("Memuat konfigurasi...")
    cfg = load_config("configs/rsw_config.yaml")
    system = CentralizedHedgeFundSystem(cfg)
    
    print("Menjalankan agen AI (1 siklus)...")
    decision = system.run_cycle(execute=False) 
    
    wita_time = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S WITA")
    
    # Gunakan tag HTML untuk format
    pesan = "---------------------------------\n"
    pesan += "🤖 <b>RSW AI HEDGE FUND REPORT</b>\n"
    pesan += "---------------------------------\n"
    pesan += f"🕒 {wita_time}\n\n"
    pesan += "<b>Alokasi Portofolio:</b>\n"
    
    sorted_weights = sorted(decision.target_weights.items(), key=lambda x: abs(x[1]), reverse=True)
    
    ada_aset = False
    for symbol, weight in sorted_weights:
        if abs(weight) > 0.01: 
            emoji = "🟢" if weight > 0 else "🔴"
            pesan += f"{emoji} <code>{symbol}</code>: {weight*100:.1f}%\n"
            ada_aset = True
            
    if not ada_aset:
        pesan += "<i>Semua aset dalam status Cash (0%)</i>\n"
        
    pesan += "\n<b>Status Risiko:</b>\n"
    if decision.risk_flags:
        pesan += f"⚠️ {', '.join(decision.risk_flags)}\n"
    else:
        pesan += "✅ Normal\n"
        
    pesan += "---------------------------------\n"
    pesan += "<i>Laporan dari AI Native Hedge Fund</i>"
    
    print("\n--- ISI PESAN YANG AKAN DIKIRIM ---")
    print(pesan)
    print("-----------------------------------\n")
    
    send_telegram(pesan)
    print("Selesai!")

if __name__ == "__main__":
    main()
