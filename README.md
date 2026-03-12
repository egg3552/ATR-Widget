# ATR Widget

A lightweight, always-on-top desktop widget for **macOS and Windows** that displays the current **Average True Range (ATR)** in **pips / points** for any market instrument.

---

## Features

- 📈 **Live ATR(14)** in pips for Forex, Indices, Commodities, and Crypto
- 🔄 **Auto-refreshes** every 30 seconds (configurable in `atr_widget.py`)
- 🎯 **Correct pip scaling** — JPY pairs use 2dp, standard forex 4dp, indices/commodities use points
- 🗂 **20+ symbols** built-in: EUR/USD, GBP/USD, S&P 500, Gold, BTC/USD, etc.
- ⏱ **Multiple timeframes**: 1m, 5m, 15m, 30m, 1h, Daily, Weekly
- 🖥 **Always-on-top** floating window — drag it anywhere
- ⚡ **Background data fetch** — UI never freezes

---

## Requirements

- Python 3.8+
- Internet connection (uses Yahoo Finance)

---

## Installation

```bash
# 1. Clone / download the project
cd ATRwidget

# 2. Create a virtual environment
python3 -m venv .venv

# 3. Activate it
source .venv/bin/activate        # macOS/Linux
.venv\Scripts\activate           # Windows

# 4. Install dependencies
pip install -r requirements.txt
```

---

## Running

**macOS / Linux:**
```bash
chmod +x run.sh
./run.sh
# OR directly:
.venv/bin/python atr_widget.py
```

**Windows:**
```
run.bat
```

---

## Configuration

Open `atr_widget.py` and edit the top section:

| Variable          | Default | Description                        |
|-------------------|---------|------------------------------------|
| `ATR_PERIOD`      | `14`    | ATR period (bars)                  |
| `REFRESH_SECONDS` | `30`    | How often to refresh data          |
| `SYMBOLS`         | —       | Add/remove instruments here        |
| `TIMEFRAMES`      | —       | Add/remove timeframes here         |

---

## How ATR is converted to pips

| Instrument        | 1 pip =      |
|-------------------|--------------|
| Forex (non-JPY)   | 0.0001       |
| Forex JPY pairs   | 0.01         |
| Indices / Crypto / Commodities | 1 point |

---

## Data Source

Market data is fetched via **Yahoo Finance** (`yfinance`). Data is delayed ~15 minutes for most instruments. This widget is for **informational purposes only** and is not financial advice.
# ATR-Widget
