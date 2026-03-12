"""
ATR Widget — Cross-platform desktop widget (macOS & Windows)
Displays the Average True Range (ATR) in pips for any market symbol.
Aesthetic: Apple Liquid Glass — frosted blur, gradient depth, specular rim.

Run: python atr_widget.py
"""

import customtkinter as ctk
import tkinter as tk
import threading
import time
import math
import yfinance as yf
import pandas as pd
from ta.volatility import AverageTrueRange
from PIL import Image, ImageDraw, ImageFilter, ImageChops, ImageTk

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
# LIQUID GLASS GUI
# ──────────────────────────────────────────────

# Window dimensions
W, H = 340, 260
CORNER = 22

# Colour tokens — Apple liquid glass palette
GLASS_TOP    = (255, 255, 255, 38)   # white frost at top (RGBA)
GLASS_BOT    = (120, 140, 180, 18)   # cool blue tint at bottom
GRAD_A       = (15,  20,  45)        # deep navy (base gradient start)
GRAD_B       = (30,  55,  100)       # royal blue
SPEC_COL     = (255, 255, 255, 70)   # specular highlight rim
ACCENT_RGB   = (80,  220, 180)       # mint-green accent
ACCENT_HEX   = "#50dcb4"
ACCENT2_HEX  = "#ff6b8a"
AMBER_HEX    = "#ffb340"
TEXT_HI      = "#ffffff"
TEXT_MID     = "rgba(255,255,255,0.72)"
TEXT_DIM     = "#8a9bb5"
import sys
FONT_SAN = "Helvetica Neue"   # will use SF Pro if available on macOS at runtime


def _lerp_color(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def make_glass_background(w: int, h: int, radius: int) -> Image.Image:
    """
    Build a liquid-glass RGBA image:
      1. Deep gradient base (navy → royal blue, top-left lit)
      2. Frosted white veil
      3. Rounded-rect mask
      4. Subtle Gaussian blur for the frosted feel
      5. Specular rim on top edge
    """
    # --- base gradient (diagonal) ---
    base = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    for y in range(h):
        t = y / (h - 1)
        # diagonal tint: add horizontal variation
        row = Image.new("RGBA", (w, 1))
        for x in range(w):
            tx = x / (w - 1)
            blend = (t + tx) / 2
            rgb = _lerp_color(GRAD_A, GRAD_B, blend)
            row.putpixel((x, 0), (*rgb, 255))
        base.paste(row, (0, y))

    # --- frosted glass veil (top half brighter) ---
    veil = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    vd = ImageDraw.Draw(veil)
    for y in range(h):
        t = 1 - (y / h)   # strong at top, fades down
        alpha = int(GLASS_TOP[3] * t + GLASS_BOT[3] * (1 - t))
        r = int(GLASS_TOP[0] * t + GLASS_BOT[0] * (1 - t))
        g = int(GLASS_TOP[1] * t + GLASS_BOT[1] * (1 - t))
        b = int(GLASS_TOP[2] * t + GLASS_BOT[2] * (1 - t))
        vd.line([(0, y), (w, y)], fill=(r, g, b, alpha))
    base = Image.alpha_composite(base, veil)

    # --- rounded rect mask ---
    mask = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=255)
    base.putalpha(mask)

    # --- soft bloom / blur pass (applied only to veil layer for glass depth)
    bloom = base.filter(ImageFilter.GaussianBlur(radius=2))
    base = Image.blend(base.convert("RGBA"), bloom.convert("RGBA"), alpha=0.25)
    base.putalpha(mask)  # reapply after blend

    # --- specular highlight — thin bright strip at top ---
    spec = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(spec)
    highlight_h = max(4, h // 14)
    for y in range(highlight_h):
        t = 1 - (y / highlight_h)
        a = int(SPEC_COL[3] * t * t)   # quadratic fade
        sd.line([(radius, y), (w - radius, y)], fill=(*SPEC_COL[:3], a))
    # round the spec ends with a simple mask intersection
    spec_mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(spec_mask).rounded_rectangle(
        [0, 0, w - 1, highlight_h * 2], radius=radius, fill=255
    )
    spec_alpha = spec.split()[3]
    spec.putalpha(ImageChops.darker(spec_alpha, spec_mask))
    base = Image.alpha_composite(base, spec)

    # --- inner border glow ---
    border = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    bd = ImageDraw.Draw(border)
    bd.rounded_rectangle([0, 0, w - 1, h - 1], radius=radius,
                         outline=(255, 255, 255, 45), width=1)
    base = Image.alpha_composite(base, border)

    return base


def make_card_bg(w: int, h: int, radius: int = 14) -> Image.Image:
    """Smaller inner glass card — lighter frost."""
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=radius,
                        fill=(255, 255, 255, 22))
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=radius,
                        outline=(255, 255, 255, 55), width=1)
    # top highlight strip
    for y in range(3):
        a = int(80 * (1 - y / 3))
        d.line([(radius, y), (w - radius, y)], fill=(255, 255, 255, a))
    return img


ctk.set_appearance_mode("dark")


class ATRWidget(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.overrideredirect(True)          # frameless

        # Transparent window background so rounded corners show through
        import platform
        if platform.system() == "Darwin":
            self.attributes("-transparent", True)
            self.configure(fg_color="systemTransparent")
        elif platform.system() == "Windows":
            self.attributes("-transparentcolor", "#010203")
            self.configure(fg_color="#010203")
        else:
            self.configure(fg_color="#010203")

        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{W}x{H}+{sw - W - 30}+{sh // 2 - H // 2}")

        self._drag_x   = 0
        self._drag_y   = 0
        self._job      = None
        self._fetching = False
        self._pulse    = 0.0
        self._pulse_dir = 1

        self._sym_map = {}
        for items in SYMBOLS.values():
            self._sym_map.update(items)

        self._build_ui()
        self._animate()
        self._schedule(delay_ms=300)

    # ── Render glass background ──────────────────────

    def _render_background(self):
        img = make_glass_background(W, H, CORNER)
        self._bg_photo = ImageTk.PhotoImage(img)
        self._canvas.itemconfig(self._bg_item, image=self._bg_photo)

        card_w, card_h = W - 32, 90
        card_img = make_card_bg(card_w, card_h)
        self._card_photo = ImageTk.PhotoImage(card_img)
        self._canvas.itemconfig(self._card_item, image=self._card_photo)

    # ── Build UI ─────────────────────────────────────

    def _build_ui(self):
        # Canvas is the entire window — glass drawn here
        canvas_bg = "systemTransparent" if __import__("platform").system() == "Darwin" else "#010203"
        self._canvas = tk.Canvas(
            self, width=W, height=H,
            bg=canvas_bg, highlightthickness=0, bd=0,
        )
        self._canvas.place(x=0, y=0)

        # Background glass layer
        placeholder = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        self._bg_photo = ImageTk.PhotoImage(placeholder)
        self._bg_item  = self._canvas.create_image(0, 0, anchor="nw", image=self._bg_photo)

        # Inner card
        card_w, card_h = W - 32, 90
        card_placeholder = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
        self._card_photo = ImageTk.PhotoImage(card_placeholder)
        self._card_item  = self._canvas.create_image(16, 110, anchor="nw", image=self._card_photo)

        # Accent glow orb (animated)
        self._orb = self._canvas.create_oval(
            W // 2 - 60, 95, W // 2 + 60, 175,
            fill="", outline="", stipple=""
        )

        self._render_background()

        # ── Close button (top-right) ─────────────────
        btn_bg = "systemTransparent" if __import__("platform").system() == "Darwin" else "#010203"
        close_btn = tk.Label(
            self._canvas, text="✕",
            bg=btn_bg, fg="#ffffff",
            font=("Helvetica Neue", 11), cursor="hand2",
        )
        self._canvas.create_window(W - 18, 18, window=close_btn, anchor="center")
        close_btn.bind("<Button-1>", lambda _: self.destroy())

        # ── Pulse dot (top-left status) ───────────────
        self._dot_id = self._canvas.create_oval(
            18, 14, 26, 22, fill="#334466", outline=""
        )

        # ── Title label ───────────────────────────────
        self._canvas.create_text(
            W // 2, 20,
            text="ATR  WIDGET",
            fill="#aabbd4",
            font=("Helvetica Neue", 9, "bold"),
            anchor="center",
            tags="title",
        )

        # ── ATR big number ────────────────────────────
        self._atr_id = self._canvas.create_text(
            W // 2, 148,
            text="—",
            fill=ACCENT_HEX,
            font=("Helvetica Neue", 46, "bold"),
            anchor="center",
        )

        # ── Unit label ────────────────────────────────
        self._unit_id = self._canvas.create_text(
            W // 2, 191,
            text=f"pips  ·  ATR {ATR_PERIOD}",
            fill="#8ab4d4",
            font=("Helvetica Neue", 10),
            anchor="center",
        )

        # ── Controls row (symbol + timeframe) ────────
        ctrl_y = 48

        # Symbol dropdown
        self.sym_var = ctk.StringVar(value="EUR/USD")
        sym_menu = ctk.CTkOptionMenu(
            self._canvas,
            variable=self.sym_var,
            values=list(self._sym_map.keys()),
            fg_color="#1a3050",
            button_color="#1a3050",
            button_hover_color="#1e3a5f",
            dropdown_fg_color="#12243e",
            dropdown_hover_color="#1e3a5f",
            text_color="#d0e8ff",
            font=("Helvetica Neue", 11),
            width=148, height=28,
            corner_radius=10,
            command=lambda _: self._on_change(),
        )
        self._canvas.create_window(14, ctrl_y, anchor="nw", window=sym_menu)

        # Timeframe dropdown
        self.tf_var = ctk.StringVar(value="Daily")
        tf_menu = ctk.CTkOptionMenu(
            self._canvas,
            variable=self.tf_var,
            values=list(TIMEFRAMES.keys()),
            fg_color="#1a3050",
            button_color="#1a3050",
            button_hover_color="#1e3a5f",
            dropdown_fg_color="#12243e",
            dropdown_hover_color="#1e3a5f",
            text_color="#d0e8ff",
            font=("Helvetica Neue", 11),
            width=110, height=28,
            corner_radius=10,
            command=lambda _: self._on_change(),
        )
        self._canvas.create_window(170, ctrl_y, anchor="nw", window=tf_menu)

        # Refresh button
        ref_btn = ctk.CTkButton(
            self._canvas,
            text="⟳",
            width=36, height=28,
            fg_color="#1a3050",
            hover_color="#1e4a30",
            text_color=ACCENT_HEX,
            font=("Helvetica Neue", 16),
            corner_radius=10,
            border_width=1,
            border_color="#50dcb4",
            command=self._manual_refresh,
        )
        self._canvas.create_window(288, ctrl_y, anchor="nw", window=ref_btn)

        # ── Footer row ────────────────────────────────
        self._price_id = self._canvas.create_text(
            16, H - 14,
            text="Price  —",
            fill="#5a7a9a",
            font=("Helvetica Neue", 9),
            anchor="w",
        )
        self._time_id = self._canvas.create_text(
            W - 16, H - 14,
            text="",
            fill="#3a5a7a",
            font=("Helvetica Neue", 8),
            anchor="e",
        )

        # ── Drag bindings (canvas + title area) ───────
        self._canvas.bind("<ButtonPress-1>",  self._drag_start)
        self._canvas.bind("<B1-Motion>",      self._drag_motion)

    # ── Glow orb animation ───────────────────────────

    def _animate(self):
        """Pulse the accent glow orb subtly."""
        self._pulse += 0.04 * self._pulse_dir
        if self._pulse >= 1.0:
            self._pulse_dir = -1
        elif self._pulse <= 0.0:
            self._pulse_dir = 1

        alpha = int(18 + 14 * math.sin(self._pulse * math.pi))
        r, g, b = ACCENT_RGB
        # Simulate glow by changing orb colour (no true alpha in tk oval)
        hex_col = f"#{r:02x}{g:02x}{b:02x}"
        # Draw glow via canvas gradient approximation — layered ovals
        self._canvas.delete("glow")
        cx, cy = W // 2, 152
        for i in range(5, 0, -1):
            rad = 38 + i * 10
            a_frac = (alpha / 255) * (i / 5) * 0.35
            a_int = int(a_frac * 255)
            gr = min(255, int(r * 0.6))
            gg = min(255, int(g * 0.9))
            gb = min(255, int(b * 0.85))
            col = f"#{gr:02x}{gg:02x}{gb:02x}"
            self._canvas.create_oval(
                cx - rad, cy - rad // 2,
                cx + rad, cy + rad // 2,
                fill=col, outline="", tags="glow",
            )
        # Keep glow below text
        self._canvas.tag_lower("glow", self._atr_id)
        self._canvas.tag_lower("glow", self._card_item)

        self.after(50, self._animate)

    # ── Drag ─────────────────────────────────────────

    def _drag_start(self, e):
        self._drag_x = e.x_root - self.winfo_x()
        self._drag_y = e.y_root - self.winfo_y()

    def _drag_motion(self, e):
        self.geometry(f"+{e.x_root - self._drag_x}+{e.y_root - self._drag_y}")

    # ── Refresh logic ────────────────────────────────

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
            self._canvas.itemconfig(self._atr_id,  text="ERR",  fill=ACCENT2_HEX)
            self._canvas.itemconfig(self._unit_id, text=result["error"][:40])
            self._canvas.itemconfig(self._price_id, text="Price  —")
            self._canvas.itemconfig(self._dot_id, fill="#ff4455")
        else:
            v     = result["atr_pips"]
            price = result["current_price"]
            unit  = result["unit"]

            atr_str   = f"{v:,.1f}" if v >= 100 else f"{v:.2f}"
            price_str = (f"{price:,.2f}" if price >= 1000
                         else f"{price:.4f}" if price >= 1
                         else f"{price:.6f}")

            self._canvas.itemconfig(self._atr_id,  text=atr_str, fill=ACCENT_HEX)
            self._canvas.itemconfig(self._unit_id, text=f"{unit}  ·  ATR {ATR_PERIOD}")
            self._canvas.itemconfig(self._price_id, text=f"Price  {price_str}")
            self._canvas.itemconfig(self._dot_id, fill=ACCENT_HEX)

        ts = time.strftime("%H:%M:%S")
        self._canvas.itemconfig(self._time_id, text=ts)
        self._schedule()

    def _set_loading(self):
        self._canvas.itemconfig(self._atr_id,  text="···", fill="#4a6a8a")
        self._canvas.itemconfig(self._unit_id, text="fetching…")
        self._canvas.itemconfig(self._dot_id,  fill=AMBER_HEX)


# ──────────────────────────────────────────────
# ENTRY POINT
# ──────────────────────────────────────────────

if __name__ == "__main__":
    app = ATRWidget()
    app.mainloop()
