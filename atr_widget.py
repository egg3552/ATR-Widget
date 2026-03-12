"""
ATR Widget — Cross-platform desktop widget (macOS & Windows)
Displays the Average True Range (ATR) in pips for any market symbol.

Run: python atr_widget.py
"""

import customtkinter as ctk
import threading
import time
import yfinance as yf
import pandas as pd
from ta.volatility import AverageTrueRange

# ──────────────────────────────────────────────
# CONFIGURATION
# ──────────────────────────────────────────────

# Popular symbols grouped by category
SYMBOLS = {
    "Forex": {
        "EUR/USD": "EURUSD=X",
        "GBP/USD": "GBPUSD=X",
        "USD/JPY": "USDJPY=X",
        "AUD/USD": "AUDUSD=X",
        "USD/CAD": "USDCAD=X",
        "USD/CHF": "USDCHF=X",
        "NZD/USD": "NZDUSD=X",
        "GBP/JPY": "GBPJPY=X",
        "EUR/JPY": "EURJPY=X",
        "EUR/GBP": "EURGBP=X",
    },
    "Indices": {
        "S&P 500":   "^GSPC",
        "NASDAQ 100": "^NDX",
        "Dow Jones": "^DJI",
        "FTSE 100":  "^FTSE",
        "DAX 40":    "^GDAXI",
        "Nikkei 225":"^N225",
    },
    "Commodities": {
        "Gold":      "GC=F",
        "Silver":    "SI=F",
        "Crude Oil": "CL=F",
        "Nat. Gas":  "NG=F",
    },
    "Crypto": {
        "BTC/USD":  "BTC-USD",
        "ETH/USD":  "ETH-USD",
        "XRP/USD":  "XRP-USD",
    },
}

TIMEFRAMES = {
    "1 min":   {"period": "1d",  "interval": "1m"},
    "5 min":   {"period": "5d",  "interval": "5m"},
    "15 min":  {"period": "5d",  "interval": "15m"},
    "30 min":  {"period": "1mo", "interval": "30m"},
    "1 Hour":  {"period": "1mo", "interval": "60m"},
    "4 Hour":  {"period": "3mo", "interval": "1d"},   # yfinance: 4h not supported; use Daily
    "Daily":   {"period": "1y",  "interval": "1d"},
    "Weekly":  {"period": "5y",  "interval": "1wk"},
}

ATR_PERIOD = 14          # standard ATR period
REFRESH_SECONDS = 30     # how often to refresh data


# ──────────────────────────────────────────────
# PIP VALUE LOGIC
# ──────────────────────────────────────────────

def get_pip_divisor(ticker_symbol: str) -> float:
    """
    Returns the divisor to convert price units → pips.
    - Forex (non-JPY): 1 pip = 0.0001  → divisor 0.0001
    - JPY pairs:       1 pip = 0.01    → divisor 0.01
    - Indices / Gold / Oil / Crypto: 1 pip = 1 point  → divisor 1
    """
    sym = ticker_symbol.upper()
    if "JPY" in sym:
        return 0.01
    # Forex: ticker contains =X
    if "=X" in sym:
        return 0.0001
    # Everything else treated as points (divisor = 1)
    return 1.0


def pip_label(ticker_symbol: str) -> str:
    """Return the correct unit label for the instrument."""
    if "=X" in ticker_symbol:
        return "pips"
    return "pts"


# ──────────────────────────────────────────────
# DATA FETCHING & ATR CALCULATION
# ──────────────────────────────────────────────

def fetch_atr(ticker_symbol: str, timeframe_key: str) -> dict:
    """
    Download OHLCV data and compute ATR(14).
    Returns a dict with keys: atr_value, atr_pips, current_price, unit, error.
    """
    try:
        tf = TIMEFRAMES[timeframe_key]
        df = yf.download(
            ticker_symbol,
            period=tf["period"],
            interval=tf["interval"],
            auto_adjust=True,
            progress=False,
        )

        if df is None or df.empty:
            return {"error": "No data returned"}

        # pandas_ta ATR
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
        atr_indicator = AverageTrueRange(
            high=df["High"], low=df["Low"], close=df["Close"],
            window=ATR_PERIOD, fillna=False,
        )
        df["ATR"] = atr_indicator.average_true_range()

        latest_atr = df["ATR"].dropna().iloc[-1]
        latest_price = df["Close"].iloc[-1]

        divisor = get_pip_divisor(ticker_symbol)
        atr_pips = latest_atr / divisor
        unit = pip_label(ticker_symbol)

        return {
            "atr_value": latest_atr,
            "atr_pips": atr_pips,
            "current_price": latest_price,
            "unit": unit,
            "error": None,
        }

    except Exception as exc:
        return {"error": str(exc)}


# ──────────────────────────────────────────────
# GUI — MAIN WIDGET (customtkinter)
# ──────────────────────────────────────────────

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

ACCENT  = "#00d4aa"
ACCENT2 = "#ff6b6b"
AMBER   = "#f5a623"
CARD    = "#0f3460"
DARK    = "#16213e"
BASE    = "#1a1a2e"
FG      = "#e0e0e0"
FONT    = "Helvetica"


class ATRWidget(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("ATR Widget")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.configure(fg_color=BASE)

        # Place top-right of screen
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        self.geometry(f"320x240+{sw - 340}+40")

        self._drag_x   = 0
        self._drag_y   = 0
        self._job      = None
        self._fetching = False

        # Flat symbol map
        self._sym_map = {}
        for items in SYMBOLS.values():
            self._sym_map.update(items)

        self._build_ui()
        self._schedule(delay_ms=200)

    # ── Build UI ────────────────────────────────────

    def _build_ui(self):

        # Title bar
        title_bar = ctk.CTkFrame(self, fg_color=DARK, height=36, corner_radius=0)
        title_bar.pack(fill="x")
        title_bar.pack_propagate(False)

        ctk.CTkLabel(
            title_bar, text="📈  ATR Widget",
            font=(FONT, 13, "bold"), text_color=FG,
        ).pack(side="left", padx=12, pady=6)

        self.dot = ctk.CTkLabel(
            title_bar, text="●", font=(FONT, 11), text_color="#444444",
        )
        self.dot.pack(side="right", padx=12)

        # Make title bar draggable
        for w in [title_bar] + title_bar.winfo_children():
            w.bind("<ButtonPress-1>", self._drag_start)
            w.bind("<B1-Motion>",     self._drag_motion)

        # Controls row
        ctrl = ctk.CTkFrame(self, fg_color=BASE, corner_radius=0)
        ctrl.pack(fill="x", padx=12, pady=(8, 4))

        ctk.CTkLabel(ctrl, text="Symbol",    font=(FONT, 9), text_color=FG
                     ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(ctrl, text="Timeframe", font=(FONT, 9), text_color=FG
                     ).grid(row=0, column=1, sticky="w", padx=(10, 0))

        self.sym_var = ctk.StringVar(value="EUR/USD")
        ctk.CTkOptionMenu(
            ctrl, variable=self.sym_var,
            values=list(self._sym_map.keys()),
            fg_color=CARD, button_color=CARD,
            button_hover_color="#1a4a80",
            dropdown_fg_color=CARD,
            text_color=FG, font=(FONT, 11), width=140,
            command=lambda _: self._on_change(),
        ).grid(row=1, column=0)

        self.tf_var = ctk.StringVar(value="Daily")
        ctk.CTkOptionMenu(
            ctrl, variable=self.tf_var,
            values=list(TIMEFRAMES.keys()),
            fg_color=CARD, button_color=CARD,
            button_hover_color="#1a4a80",
            dropdown_fg_color=CARD,
            text_color=FG, font=(FONT, 11), width=100,
            command=lambda _: self._on_change(),
        ).grid(row=1, column=1, padx=(10, 0))

        ctk.CTkButton(
            ctrl, text="⟳", width=36, height=28,
            fg_color=ACCENT, hover_color="#00b894",
            text_color=BASE, font=(FONT, 14, "bold"),
            command=self._manual_refresh,
        ).grid(row=1, column=2, padx=(8, 0))

        # ATR card
        card = ctk.CTkFrame(self, fg_color=CARD, corner_radius=10)
        card.pack(fill="x", padx=12, pady=6)

        self.atr_label = ctk.CTkLabel(
            card, text="—",
            font=(FONT, 40, "bold"), text_color=ACCENT,
        )
        self.atr_label.pack(pady=(10, 0))

        self.unit_label = ctk.CTkLabel(
            card, text=f"pips  (ATR {ATR_PERIOD})",
            font=(FONT, 10), text_color=FG,
        )
        self.unit_label.pack(pady=(0, 10))

        # Footer
        footer = ctk.CTkFrame(self, fg_color=BASE, corner_radius=0)
        footer.pack(fill="x", padx=12, pady=(0, 6))

        self.price_label = ctk.CTkLabel(
            footer, text="Price: —", font=(FONT, 9), text_color=FG,
        )
        self.price_label.pack(side="left")

        self.time_label = ctk.CTkLabel(
            footer, text="", font=(FONT, 8), text_color="#666666",
        )
        self.time_label.pack(side="right")

    # ── Drag ────────────────────────────────────────

    def _drag_start(self, e):
        self._drag_x = e.x_root - self.winfo_x()
        self._drag_y = e.y_root - self.winfo_y()

    def _drag_motion(self, e):
        self.geometry(f"+{e.x_root - self._drag_x}+{e.y_root - self._drag_y}")

    # ── Refresh ─────────────────────────────────────

    def _on_change(self):
        if self._job:
            self.after_cancel(self._job)
        self._schedule(delay_ms=200)

    def _manual_refresh(self):
        if self._job:
            self.after_cancel(self._job)
        self._schedule(delay_ms=0)

    def _schedule(self, delay_ms=None):
        ms = REFRESH_SECONDS * 1000 if delay_ms is None else delay_ms
        self._job = self.after(ms, self._do_refresh)

    def _do_refresh(self):
        if self._fetching:
            self._schedule()
            return
        self._fetching = True
        self._set_loading()
        threading.Thread(target=self._bg_fetch, daemon=True).start()

    def _bg_fetch(self):
        ticker = self._sym_map.get(self.sym_var.get(), self.sym_var.get())
        result = fetch_atr(ticker, self.tf_var.get())
        self.after(0, lambda: self._update_ui(result))

    def _update_ui(self, result: dict):
        self._fetching = False
        if result.get("error"):
            self.atr_label.configure(text="ERR",  text_color=ACCENT2)
            self.unit_label.configure(text=result["error"][:45])
            self.price_label.configure(text="Price: —")
            self.dot.configure(text_color=ACCENT2)
        else:
            v     = result["atr_pips"]
            price = result["current_price"]
            unit  = result["unit"]

            atr_str   = f"{v:,.1f}" if v >= 100 else f"{v:.2f}"
            price_str = (f"{price:,.2f}" if price >= 1000
                         else f"{price:.4f}" if price >= 1
                         else f"{price:.6f}")

            self.atr_label.configure(text=atr_str, text_color=ACCENT)
            self.unit_label.configure(text=f"{unit}  (ATR {ATR_PERIOD})")
            self.price_label.configure(text=f"Price: {price_str}")
            self.dot.configure(text_color=ACCENT)

        self.time_label.configure(text=f"Updated {time.strftime('%H:%M:%S')}")
        self._schedule()

    def _set_loading(self):
        self.atr_label.configure(text="…", text_color="#888888")
        self.unit_label.configure(text="Fetching data…")
        self.dot.configure(text_color=AMBER)


# ──────────────────────────────────────────────
# ENTRY POINT
# ──────────────────────────────────────────────

if __name__ == "__main__":
    app = ATRWidget()
    app.mainloop()
