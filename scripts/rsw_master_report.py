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
import rsw_settings as cfg

warnings.filterwarnings("ignore")
sys.stdout.reconfigure(line_buffering=True)

# TELEGRAM CONFIG
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_FOREX = os.getenv("TELEGRAM_CHAT_ID_FOREX")
CHAT_ETF = os.getenv("TELEGRAM_CHAT_ID_ETF")
CHAT_CRYPTO = os.getenv("TELEGRAM_CHAT_ID_CRYPTO")

def send_telegram(chat_id, message):
    if not TOKEN or not chat_id: return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    for i in range(0, len(message), 4000):
        requests.post(url, json={"chat_id": chat_id, "text": message[i:i+4000], "parse_mode": "HTML"}, timeout=15)

# DAFTAR ASET
CRYPTO = [("BTC", "BTC-USD"), ("ETH", "ETH-USD"), ("AAVE", "AAVE-USD"), ("SOL", "SOL-USD"), ("XRP", "XRP-USD"), ("NEAR", "NEAR-USD")]
ETF = [("QQQM", "QQQM"), ("VTI", "VTI"), ("VEA", "VEA"), ("SCHD", "SCHD"), ("SCHG", "SCHG"), ("SOXX", "SOXX"), ("AVUV", "AVUV"), ("VUG", "VUG"), ("VXUS", "VXUS"), ("VYM", "VYM"), ("VOO", "VOO"), ("VB", "VB")]
GOLD = [("XAUUSD", "GC=F")]
FOREX = [("EURUSD", "EURUSD=X"), ("GBPUSD", "GBPUSD=X"), ("USDJPY", "USDJPY=X"), ("AUDUSD", "AUDUSD=X"), ("USDCAD", "USDCAD=X"), ("USDCHF", "USDCHF=X"), ("NZDUSD", "NZDUSD=X"), ("EURGBP", "EURGBP=X"), ("EURJPY", "EURJPY=X"), ("GBPJPY", "GBPJPY=X"), ("EURAUD", "EURAUD=X"), ("EURCHF", "EURCHF=X"), ("EURCAD", "EURCAD=X"), ("GBPCHF", "GBPCHF=X"), ("GBPCAD", "GBPCAD=X"), ("AUDCAD", "AUDCAD=X"), ("AUDCHF", "AUDCHF=X"), ("AUDNZD", "AUDNZD=X"), ("NZDCAD", "NZDCAD=X"), ("NZDCHF", "NZDCHF=X"), ("CADCHF", "CADCHF=X"), ("CADJPY", "CADJPY=X"), ("CHFJPY", "CHFJPY=X"), ("AUDJPY", "AUDJPY=X"), ("NZDJPY", "NZDJPY=X"), ("EURNZD", "EURNZD=X"), ("GBPNZD", "GBPNZD=X")]

def now_wita(): return datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M WITA")

def atr(df, period=14):
    tr = pd.concat([df["High"] - df["Low"], (df["High"] - df["Close"].shift()).abs(), (df["Low"] - df["Close"].shift()).abs()], axis=1).max(axis=1)
    return float(tr.rolling(period).mean().iloc[-1])

def fisher(df, period=9):
    hl2 = (df["High"] + df["Low"]) / 2
    min_low, max_high = df["Low"].rolling(period).min(), df["High"].rolling(period).max()
    x = 2 * ((hl2 - min_low) / (max_high - min_low).replace(0, np.nan) - 0.5)
    val = 0.33 * 2 * x.clip(-0.999, 0.999) + 0.67 * x.shift(1).fillna(0)
    return (0.5 * np.log((1 + val.clip(-0.999, 0.999)) / (1 - val.clip(-0.999, 0.999)))).rolling(2).mean()

def analyze_tech(ticker, trend_tf, entry_tf, atr_tf):
    try:
        p_trend = cfg.get_yf_period(trend_tf)
        p_entry = cfg.get_yf_period(entry_tf)
        p_atr = cfg.get_yf_period(atr_tf)
        
        df_d = yf.download(ticker, period=p_trend, interval=trend_tf, progress=False)
        df_1h = yf.download(ticker, period=p_entry, interval=entry_tf, progress=False)
        df_atr = yf.download(ticker, period=p_atr, interval=atr_tf, progress=False)
        
        if df_d.empty or df_1h.empty: return None
        if isinstance(df_d.columns, pd.MultiIndex): df_d.columns = df_d.columns.get_level_values(0)
        if isinstance(df_1h.columns, pd.MultiIndex): df_1h.columns = df_1h.columns.get_level_values(0)
        if isinstance(df_atr.columns, pd.MultiIndex): df_atr.columns = df_atr.columns.get_level_values(0)
        
        price = float(df_d["Close"].iloc[-1])
        ma50 = float(df_d["Close"].rolling(50).mean().iloc[-1])
        f_entry = float(fisher(df_1h).dropna().iloc[-1])
        a = atr(df_atr)
        
        sl_dist = cfg.SL_MULTIPLIER * a
        tp_dist = cfg.TP_MULTIPLIER * a
        
        if price > ma50 and f_entry > 0:
            return {"rec": "BUY", "price": price, "sl": price - sl_dist, "tp": price + tp_dist, "conf": 75}
        elif price < ma50 and f_entry < 0:
            return {"rec": "SELL", "price": price, "sl": price + sl_dist, "tp": price - tp_dist, "conf": 75}
        return {"rec": "NETRAL", "price": price, "sl": None, "tp": None, "conf": 50}
    except Exception:
        return None

def clean_ticker_name(symbol):
    if symbol == 'GC=F': return 'XAUUSD'
    if symbol.endswith('=X'): return symbol.replace('=X', '')
    return symbol

def main():
    cfg_hf = load_config("configs/rsw_config.yaml")
    system = CentralizedHedgeFundSystem(cfg_hf)
    decision = system.run_cycle(execute=False)
    
    macro_conf = {}
    daily_bias = {}
    
    for k, v in decision.target_weights.items():
        if abs(v) >= 0.02:
            conf = int(min(100, 50 + ((abs(v) / 0.30) * 50)))
            arah = "BUY" if v > 0 else "SELL"
            macro_conf[k] = {"dir": arah, "conf": conf}
            daily_bias[k] = arah
            
    with open("daily_bias.json", "w") as f:
        json.dump(daily_bias, f, indent=4)

    # === FOREX & GOLD REPORT ===
    msg_fx = f"-------------------------------------------\nRSW AI FOREX & GOLD REPORT\n{now_wita()}\n-------------------------------------------\n\n"
    msg_fx += f"ARAHAN MAKRO ({cfg.MACRO_TIMEFRAME.upper()})\n\n"
    if not macro_conf:
        msg_fx += "Tidak ada arahan makro yang kuat saat ini.\n"
    else:
        for k, v in macro_conf.items():
            if k.endswith("=X") or k == "GC=F":
                emoji = "🟢" if v['dir'] == "BUY" else "🔴"
                status = "KUAT" if v['conf'] >= 75 else ("SEDANG" if v['conf'] >= 60 else "LEMAH")
                msg_fx += f"{emoji} {clean_ticker_name(k)} | {v['dir']}\nConfidence: {v['conf']}% ({status})\n\n"
    
    msg_fx += f"-------------------------------------------\nFOREX & GOLD (TEKNIKAL)\nTF: {cfg.FX_TREND_TF.upper()} Trend / {cfg.FX_ENTRY_TF.upper()} Entry\n-------------------------------------------\n\n"
    for name, ticker in (FOREX + GOLD):
        tech = analyze_tech(ticker, cfg.FX_TREND_TF, cfg.FX_ENTRY_TF, cfg.FX_ATR_TF)
        if not tech: continue
        if tech['rec'] == "NETRAL":
            msg_fx += f"⚪ {name} [NETRAL]\nConfidence: 50% (LEMAH)\n\n"
        else:
            emoji = "🟢" if tech['rec'] == "BUY" else "🔴"
            msg_fx += f"{emoji} {name} [{tech['rec']}]\n├ Entry: {tech['price']:.5g}\n├ SL: {tech['sl']:.5g}\n└ TP: {tech['tp']:.5g}\nConfidence: {tech['conf']}% (KUAT)\n\n"
    send_telegram(CHAT_FOREX, msg_fx.rstrip())

    # === ETF REPORT ===
    msg_etf = f"-------------------------------------------\nRSW AI ETF REPORT\n{now_wita()}\n-------------------------------------------\n\nETF (TEKNIKAL)\nTF: {cfg.ETF_TREND_TF.upper()} Trend / {cfg.ETF_ENTRY_TF.upper()} Entry\n-------------------------------------------\n\n"
    for name, ticker in ETF:
        tech = analyze_tech(ticker, cfg.ETF_TREND_TF, cfg.ETF_ENTRY_TF, cfg.ETF_TREND_TF)
        if not tech: continue
        if tech['rec'] == "NETRAL":
            msg_etf += f"⚪ {name} [NETRAL]\nConfidence: 50% (LEMAH)\n\n"
        else:
            emoji = "🟢" if tech['rec'] == "BUY" else "🔴"
            msg_etf += f"{emoji} {name} [{tech['rec']}]\n├ Price: {tech['price']:.5g}\n├ SL: {tech['sl']:.5g}\n└ TP: {tech['tp']:.5g}\nConfidence: {tech['conf']}% (KUAT)\n\n"
    send_telegram(CHAT_ETF, msg_etf.rstrip())

    # === CRYPTO REPORT ===
    msg_crypto = f"-------------------------------------------\nRSW AI CRYPTO REPORT\n{now_wita()}\n-------------------------------------------\n\nCRYPTO (TEKNIKAL)\nTF: {cfg.CRYPTO_TREND_TF.upper()} Trend / {cfg.CRYPTO_ENTRY_TF.upper()} Entry\n-------------------------------------------\n\n"
    for name, ticker in CRYPTO:
        tech = analyze_tech(ticker, cfg.CRYPTO_TREND_TF, cfg.CRYPTO_ENTRY_TF, cfg.CRYPTO_TREND_TF)
        if not tech: continue
        if tech['rec'] == "NETRAL":
            msg_crypto += f"⚪ {name} [NETRAL]\nConfidence: 50% (LEMAH)\n\n"
        else:
            emoji = "🟢" if tech['rec'] == "BUY" else "🔴"
            msg_crypto += f"{emoji} {name} [{tech['rec']}]\n├ Entry: {tech['price']:.5g}\n├ SL: {tech['sl']:.5g}\n└ TP: {tech['tp']:.5g}\nConfidence: {tech['conf']}% (KUAT)\n\n"
    send_telegram(CHAT_CRYPTO, msg_crypto.rstrip())

if __name__ == "__main__":
    main()
