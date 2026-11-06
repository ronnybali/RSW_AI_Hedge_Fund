# =====================================================================
# RSW AI SYSTEM - CENTRALIZED CONFIGURATION
# =====================================================================

# 1. KONFIGURASI MAKRO (AI HEDGE FUND)
MACRO_TIMEFRAME = "1d" # Timeframe Acuan AI Hedge Fund (Sebaiknya tetap 1d)

# 2. KONFIGURASI TIME FRAME AI SWING (TEKNIKAL)
# Forex & Gold (Untuk VPS & Laporan)
FX_TREND_TF = "1d"     # Opsi: "1d", "4h", "1h" (Untuk MA50)
FX_ENTRY_TF = "1h"     # Opsi: "1h", "30m", "15m" (Untuk Fisher Transform)
FX_ATR_TF = "1d"       # Opsi: "1d", "4h", "1h", "15m"

# ETF (Hanya untuk Laporan GitHub - Disarankan D1)
ETF_TREND_TF = "1d"
ETF_ENTRY_TF = "1d"

# Crypto (Hanya untuk Laporan GitHub)
CRYPTO_TREND_TF = "1d"
CRYPTO_ENTRY_TF = "4h"

# 3. PENGATURAN ATR & SL/TP (HYBRID MATH-STRUCTURE)
SL_MULTIPLIER = 2.0    # Pengali ATR untuk SL (Misal: 2.0x ATR)
TP_MULTIPLIER = 4.0    # Pengali ATR untuk TP (Rasio 1:2)
USE_HYBRID_SL = True   # True = Bandingkan ATR & Swing High/Low. False = Murni ATR.

# 4. MANAJEMEN RISIKO & BATAS
RISK_PERCENT = 1.5           # Risiko per trade (% dari Balance)
MAX_DAILY_LOSS_PCT = 15.0    # Circuit Breaker (Stop trading jika rugi harian %)
MAX_SPREAD_POINTS = 175       # Batas maksimal spread (dalam points)
CLOSE_HALF_TARGET = 0.5      # Tutup setengah posisi saat profit mencapai 50% dari TP

# 5. PENGATURAN SESI (Waktu WITA / UTC+8)
SESSION_PAIRS = {
    "ASIA": ["AUDUSD", "NZDUSD", "USDJPY", "AUDJPY", "NZDJPY", "AUDNZD", "CADJPY", "CHFJPY"],
    "EUROPE": ["EURUSD", "GBPUSD", "EURGBP", "EURJPY", "GBPJPY", "EURAUD", "EURCHF", "EURCAD", "GBPCHF", "GBPCAD", "EURNZD", "GBPNZD", "XAUUSD"],
    "NY": ["USDCAD", "USDCHF", "XAUUSD", "EURUSD", "GBPUSD", "NZDCAD", "NZDCHF", "CADCHF"]
}

# 6. DAFTAR ASET (Yahoo Finance -> MT5)
PAIRS = {
    "EURUSD=X": "EURUSD", "GBPUSD=X": "GBPUSD", "USDJPY=X": "USDJPY", "AUDUSD=X": "AUDUSD", 
    "USDCAD=X": "USDCAD", "USDCHF=X": "USDCHF", "NZDUSD=X": "NZDUSD", "EURGBP=X": "EURGBP", 
    "EURJPY=X": "EURJPY", "GBPJPY=X": "GBPJPY", "EURAUD=X": "EURAUD", "EURCHF=X": "EURCHF",
    "EURCAD=X": "EURCAD", "GBPCHF=X": "GBPCHF", "GBPCAD=X": "GBPCAD", "AUDCAD=X": "AUDCAD", 
    "AUDCHF=X": "AUDCHF", "AUDNZD=X": "AUDNZD", "NZDCAD=X": "NZDCAD", "NZDCHF=X": "NZDCHF", 
    "CADCHF=X": "CADCHF", "CADJPY=X": "CADJPY", "CHFJPY=X": "CHFJPY", "AUDJPY=X": "AUDJPY",
    "NZDJPY=X": "NZDJPY", "EURNZD=X": "EURNZD", "GBPNZD=X": "GBPNZD", "GC=F": "XAUUSD"
}

# =====================================================================
# FUNGSI BANTUAN (Jangan diubah)
# =====================================================================
def get_yf_period(tf):
    if tf in ["1wk", "1d"]: return "6mo"
    if tf in ["4h", "1h"]: return "1mo"
    if tf in ["30m", "15m"]: return "5d"
    return "3mo"
