# StockApp — Groww Portfolio Dashboard

## Overview
A FastAPI-based stock dashboard that connects to the Groww trading API to display portfolio holdings, generate buy signals, and trigger alerts. Deployed on Render.

## Tech Stack
- Python 3.9, FastAPI, Uvicorn
- `growwapi` — Groww Trade API SDK (authentication, holdings, LTP, WebSocket feed)
- `yfinance` — Historical price data from Yahoo Finance
- `ta` — Technical analysis indicators (RSI, MACD, SMA, Supertrend, ATR)
- `pandas`, `numpy` — Data manipulation
- `nltk` (VADER) — News sentiment analysis
- `pyotp` — TOTP-based authentication
- `python-dotenv` — Environment config

## Project Structure
```
server.py                      — FastAPI app, HTML dashboard routes
main.py                        — CLI entry point
groww_dashboard/
  config.py                    — GrowwConfig dataclass, loads from .env
  logging_config.py            — Logging setup
  services/
    session_manager.py         — Groww auth (TOTP, checksum, direct JWT)
    portfolio.py               — Fetches holdings, computes P&L with LTP
    buy_signals.py             — Multi-strategy stock scanner (sector momentum → stock selection)
    realtime_monitor.py        — WebSocket live price monitoring
    alerts.py                  — Price drop + bearish news alerts
    news_sentiment.py          — Google News RSS + VADER sentiment
    notifications.py           — Email/SMS alert delivery
    scheduler.py               — Periodic alert scheduler
api/index.py                   — Vercel serverless entry
```

## Key Architecture Decisions
- Session is created once at startup; `SessionManager.refresh()` re-authenticates on token expiry
- `PortfolioService` auto-retries with fresh session if holdings return empty
- LTP fetched from Groww API (real-time); historical data from yfinance (daily candles)
- Buy signals use a 2-step approach: 1) identify top sectors by momentum, 2) scan individual stocks in those sectors
- Symbols returning LTP=0 are treated as delisted (P&L set to 0, not -100%)

## API Endpoints
- `GET /` — Holdings dashboard (HTML)
- `GET /signals` — Buy signals page (HTML)
- `GET /alerts` — Triggered alerts page (HTML)
- `GET /stock/{symbol}` — Stock detail with fundamentals + technicals (HTML)
- `GET /api/holdings` — Holdings JSON
- `GET /api/signals` — Signals JSON
- `GET /debug` — Debug info (IP, token status, Groww API health)

## Groww API Fields
Holdings response structure: `{"holdings": [{"trading_symbol": "...", "quantity": ..., "average_price": ..., "isin": "...", ...}]}`
LTP endpoint: `GET /v1/live-data/ltp?segment=CASH&exchange_symbols=NSE_SYMBOL`

## Buy Signal Strategies
1. Supertrend flip (bearish → bullish)
2. Golden Cross (50 SMA crosses above 200 SMA)
3. Relative Strength vs Nifty (outperforming by 5%+ over 20 days)
4. Volume Spike (2x above 20-day average)
5. RSI Breakout (crosses above 55 from below 50)
6. Momentum (price above both SMAs + RSI > 60)

## Environment Variables
- `GROWW_API_KEY` — API key or JWT token
- `GROWW_API_SECRET` — API secret (for checksum auth)
- `GROWW_TOTP_SECRET` — Base32 TOTP secret (for automated auth)
- `SMTP_EMAIL`, `SMTP_PASSWORD`, `SMTP_HOST`, `SMTP_PORT` — Email notifications
- `TWILIO_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER` — SMS notifications
- `NOTIFY_EMAIL`, `NOTIFY_PHONE` — Alert recipients

## Known Issues
- `MANGIND` and `ASMTEC` are delisted/renamed — return LTP=0
- yfinance `TATAMOTORS.NS` sometimes 404s (symbol may need update)
- Yahoo Finance API occasionally returns 401 for `.info` calls (rate limiting)
- Groww tokens expire; session auto-refreshes on failure

## Deployment
- Render (render.yaml) — production
- Vercel (vercel.json + api/index.py) — serverless alternative
