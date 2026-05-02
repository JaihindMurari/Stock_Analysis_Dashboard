# 📈 MarketPulse India — NSE/BSE Real-Time Stock Dashboard

A production-ready Flask web application that fetches, stores, analyzes, and visualizes stock data for the **Top 50 Indian equities** listed on NSE and BSE.

---

## 🗂️ Project Structure

```
nse_dashboard/
├── app/
│   ├── __init__.py           # Flask application factory
│   ├── models/
│   │   └── __init__.py       # SQLAlchemy models (Stock, Price, Indicator, Signal)
│   ├── routes/
│   │   ├── main.py           # HTML page routes (Blueprint)
│   │   └── api.py            # REST API endpoints (Blueprint)
│   ├── services/
│   │   ├── data_ingestion.py # yfinance fetch + MySQL upsert
│   │   ├── indicators.py     # SMA, EMA, RSI, MACD, Bollinger Bands
│   │   └── scheduler.py      # APScheduler (5-min polling)
│   └── utils/
│       └── stock_universe.py # Top 50 NSE stock list
├── static/
│   ├── css/main.css          # Full dark/light theme CSS
│   └── js/app.js             # ECharts builders + global utilities
├── templates/
│   ├── base.html             # Layout: sidebar, topbar, theme toggle
│   ├── dashboard.html        # Overview + KPIs + stock table
│   ├── stock_detail.html     # Candlestick + RSI + MACD per stock
│   ├── signals.html          # BUY/SELL/HOLD signal cards
│   └── trends.html           # Sector breakdown + movers charts
├── migrations/
│   └── schema.sql            # Raw SQL schema (alternative to Flask-Migrate)
├── scripts/
│   └── setup.py              # One-shot DB setup + initial data load
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── requirements.txt
├── run.py                    # App entry point
└── .env.example
```

---

## ⚙️ Prerequisites

| Tool         | Version  |
|--------------|----------|
| Python       | 3.11+    |
| MySQL        | 8.0+     |
| pip          | latest   |

---

## 🚀 Quick Start (Local)

### 1. Clone & create virtual environment

```bash
git clone <repo-url>
cd nse_dashboard
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — set DB_HOST, DB_USER, DB_PASSWORD, DB_NAME, SECRET_KEY
```

### 3. Create MySQL database

```sql
-- In MySQL client:
CREATE DATABASE nse_dashboard CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Or run the schema file directly:
```bash
mysql -u root -p < migrations/schema.sql
```

### 4. Run one-shot setup (tables + seed + initial data)

```bash
python scripts/setup.py
```

> ⏳ The initial fetch downloads 1-year of OHLCV for 50 stocks — allow **3–5 minutes**.

### 5. Start the app

```bash
flask run
# OR for production:
gunicorn --bind 0.0.0.0:5000 --workers 2 run:app
```

Open **http://localhost:5000** in your browser.

---

## 🐳 Docker Deployment

```bash
cd docker
cp ../.env.example ../.env   # Edit DB_PASSWORD etc.
docker compose up --build
```

The app runs on **http://localhost:5000**.  
After first start, seed the DB via the UI's **Seed Data** button, then click **⟳ Refresh**.

---

## 🌐 API Reference

| Method | Endpoint                      | Description                            |
|--------|-------------------------------|----------------------------------------|
| GET    | `/api/stocks`                 | All stocks with latest price snapshot  |
| GET    | `/api/stock/<symbol>`         | Full detail: prices, indicators, signal|
| GET    | `/api/stock/<symbol>/history` | OHLCV history (`?days=90`)             |
| GET    | `/api/signals`                | Latest signal per stock (`?type=BUY`)  |
| GET    | `/api/top-movers`             | Top 5 gainers & losers                 |
| GET    | `/api/market-summary`         | KPI aggregates                         |
| POST   | `/api/admin/seed`             | Seed stock universe (idempotent)       |
| POST   | `/api/admin/refresh`          | Trigger full background refresh        |
| POST   | `/api/admin/refresh/<symbol>` | Refresh one stock immediately          |

---

## 📊 Technical Indicators

| Indicator | Parameters        | Signal Use                                |
|-----------|-------------------|-------------------------------------------|
| SMA       | 20, 50, 200 days  | Trend direction, golden/death cross       |
| EMA       | 12, 26 spans      | Short-term momentum                       |
| RSI       | 14 periods        | < 30 oversold (BUY), > 70 overbought (SELL)|
| MACD      | 12/26/9           | Bullish/bearish crossover                 |
| Bollinger | 20 days, 2σ       | Volatility squeeze visualization          |

### Signal Logic (scoring system)

Each candle is scored from **−5 to +5**:

| Rule                     | Score |
|--------------------------|-------|
| RSI < 30 (oversold)      | +2    |
| RSI 30–40               | +1    |
| RSI > 70 (overbought)    | −2    |
| RSI 60–70               | −1    |
| MACD > Signal line       | +1    |
| MACD < Signal line       | −1    |
| Price > SMA-50           | +1    |
| Price < SMA-50           | −1    |
| Price > EMA-12           | +1    |
| Price < EMA-12           | −1    |
| SMA-20 > SMA-50          | +1    |
| SMA-20 < SMA-50          | −1    |

- Score **≥ 3** → **BUY**  
- Score **≤ −3** → **SELL**  
- Otherwise → **HOLD**

---

## 🔄 Data Update Mechanism

- **APScheduler** runs `incremental_update()` every **5 minutes**
- Updates are **skipped outside NSE market hours** (Mon–Fri 09:15–15:35 IST)
- All writes use **`ON DUPLICATE KEY UPDATE`** — no duplicate rows
- Failed stock fetches are logged and skipped without crashing the scheduler

---

## 🎨 UI Features

| Feature | Details |
|---------|---------|
| Dark / Light mode | Persisted in `localStorage`, toggled via sidebar |
| Responsive | Mobile-first; sidebar collapses on small screens |
| Live charts | ECharts v5 — Candlestick, Volume, RSI, MACD, Bar, Pie |
| Global search | Fuzzy symbol + name search from any page |
| Table sort | Click any column header to sort ascending/descending |
| Signal filters | Filter stocks by BUY / SELL / HOLD on all pages |
| Auto-polling | AJAX updates every 5 minutes without page reload |

---

## 🛠️ Development Tips

```bash
# Open Flask shell
flask shell

# Run migrations (if you modify models)
flask db init
flask db migrate -m "your message"
flask db upgrade

# Manually refresh one stock
from app.services.data_ingestion import refresh_single_stock
from app.models import Stock
s = Stock.query.filter_by(symbol='TCS.NS').first()
refresh_single_stock(s)
```

---

## 📦 Key Dependencies

| Package          | Purpose                                |
|------------------|----------------------------------------|
| Flask            | Web framework                          |
| Flask-SQLAlchemy | ORM + connection pooling               |
| Flask-Migrate    | Alembic migrations                     |
| yfinance         | Yahoo Finance data (free, no API key)  |
| APScheduler      | Background job scheduling              |
| pandas / numpy   | Data manipulation                      |
| PyMySQL          | MySQL driver                           |
| ECharts 5        | Interactive financial charts (CDN)     |

---

## ⚠️ Known Limitations

- **yfinance** is unofficial and may break if Yahoo Finance changes its API.
- Real-time tick data (sub-minute) requires a paid data provider.
- NSE/BSE holidays are not explicitly modeled — the scheduler uses time-of-day only.

---

## 📄 License

MIT — free for personal and commercial use.
