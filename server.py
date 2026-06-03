"""FastAPI web dashboard — Holdings + Buy Signals UI."""

import logging

import pandas as pd
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from groww_dashboard.config import GrowwConfig
from groww_dashboard.logging_config import setup_logging
from groww_dashboard.services.alerts import AlertsEngine
from groww_dashboard.services.buy_signals import BuySignalScanner
from groww_dashboard.services.news_sentiment import NewsSentimentService
from groww_dashboard.services.portfolio import PortfolioService
from groww_dashboard.services.realtime_monitor import RealtimeMonitor
from groww_dashboard.services.scheduler import AlertScheduler
from groww_dashboard.services.session_manager import SessionManager

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="Stock Dashboard")

config = GrowwConfig.from_env()
session = SessionManager(config)
groww = session.login()
portfolio_svc = PortfolioService(groww, session_manager=session)
scanner = BuySignalScanner()
news_svc = NewsSentimentService()
alerts_engine = AlertsEngine(groww)
scheduler = AlertScheduler(alerts_engine, interval_minutes=30)
scheduler.start()

# Real-time WebSocket price monitor (starts in background after server boot)
monitor = None

@app.on_event("startup")
def start_monitor():
    import threading
    def _boot_monitor():
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        global monitor
        try:
            monitor = RealtimeMonitor(groww, drop_threshold=-3.0)
            monitor.start()
        except Exception as e:
            logger.error("Realtime monitor failed to start: %s", e)
    threading.Thread(target=_boot_monitor, daemon=True).start()

HTML_HEAD = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Stock Dashboard</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0f0f0f;color:#e0e0e0;padding:20px}
h1{font-size:1.8rem;margin-bottom:8px;color:#fff}
.subtitle{color:#888;margin-bottom:24px;font-size:0.9rem}
.tabs{display:flex;gap:8px;margin-bottom:24px}
.tab{padding:10px 20px;border-radius:8px;cursor:pointer;border:1px solid #333;background:#1a1a1a;color:#ccc;text-decoration:none;font-size:0.9rem}
.tab.active{background:#2563eb;border-color:#2563eb;color:#fff}
.card{background:#1a1a1a;border-radius:12px;padding:20px;margin-bottom:20px;border:1px solid #262626}
.summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px;margin-bottom:24px}
.metric{background:#111;border-radius:8px;padding:16px;text-align:center}
.metric-value{font-size:1.5rem;font-weight:700;margin-top:4px}
.metric-label{font-size:0.75rem;color:#888;text-transform:uppercase}
.green{color:#22c55e}.red{color:#ef4444}.blue{color:#3b82f6}
table{width:100%;border-collapse:collapse;font-size:0.85rem}
th{text-align:left;padding:12px 8px;border-bottom:1px solid #333;color:#888;font-weight:500;font-size:0.75rem;text-transform:uppercase}
td{padding:10px 8px;border-bottom:1px solid #1f1f1f}
tr:hover{background:#1f1f1f}
.badge{padding:3px 8px;border-radius:4px;font-size:0.7rem;font-weight:600}
.search-box{position:relative}
.search-box input{width:260px;padding:8px 12px;border-radius:6px;border:1px solid #333;background:#111;color:#e0e0e0;font-size:0.85rem;outline:none}
.search-box input:focus{border-color:#2563eb}
.search-results{position:absolute;top:100%;right:0;width:300px;background:#1a1a1a;border:1px solid #333;border-radius:8px;max-height:300px;overflow-y:auto;z-index:100;display:none;margin-top:4px}
.search-results a{display:block;padding:10px 16px;color:#e0e0e0;text-decoration:none;border-bottom:1px solid #262626}
.search-results a:hover{background:#262626}
.badge-gold{background:#854d0e;color:#fbbf24}
.badge-rsi{background:#1e3a5f;color:#60a5fa}
.empty{text-align:center;padding:40px;color:#666}
.header{display:flex;align-items:center;justify-content:space-between;margin-bottom:24px}
.info{display:inline-block;width:16px;height:16px;border-radius:50%;background:#333;color:#888;font-size:10px;text-align:center;line-height:16px;cursor:pointer;margin-left:4px;position:relative}
.info .tooltip{display:none;position:absolute;bottom:calc(100% + 6px);left:50%;transform:translateX(-50%);background:#262626;color:#ccc;padding:8px 12px;border-radius:6px;font-size:0.75rem;white-space:normal;width:220px;z-index:10;border:1px solid #333;line-height:1.4}
.info.active .tooltip{display:block}
@media(hover:hover){.info:hover .tooltip{display:block}}
</style>
</head>
<body>
<div class="header">
<div><h1>📊 Stock Dashboard</h1><p class="subtitle">Groww Portfolio + Buy Signals Scanner</p></div>
<div class="search-box">
<input type="text" id="stock-search" placeholder="Search stock..." autocomplete="off" aria-label="Search stocks">
<div class="search-results" id="search-results"></div>
</div>
</div>
<script>
(function(){
const input=document.getElementById('stock-search'),results=document.getElementById('search-results');
let timer;
input.addEventListener('input',function(){
  clearTimeout(timer);
  const q=this.value.trim();
  if(q.length<2){results.style.display='none';return;}
  timer=setTimeout(()=>{
    fetch('/api/search?q='+encodeURIComponent(q))
    .then(r=>r.json()).then(data=>{
      if(!data.results.length){results.innerHTML='<a href="#">No results</a>';results.style.display='block';return;}
      results.innerHTML=data.results.map(s=>'<a href="/stock/'+s.symbol+'"><strong>'+s.symbol+'</strong> — '+s.name+'</a>').join('');
      results.style.display='block';
    });
  },300);
});
input.addEventListener('keydown',function(e){
  if(e.key==='Enter'){
    const q=this.value.trim().toUpperCase();
    if(q)window.location.href='/stock/'+q;
  }
});
document.addEventListener('click',function(e){if(!e.target.closest('.search-box'))results.style.display='none';if(!e.target.closest('.info'))document.querySelectorAll('.info.active').forEach(el=>el.classList.remove('active'));});
})();
</script>"""

HTML_FOOT = "</body></html>"


def tabs_html(active: str) -> str:
    h = "active" if active == "holdings" else ""
    s = "active" if active == "signals" else ""
    a = "active" if active == "alerts" else ""
    return f'<div class="tabs"><a href="/" class="tab {h}">Holdings</a><a href="/signals" class="tab {s}">Buy Signals</a><a href="/alerts" class="tab {a}">Alerts</a></div>'


@app.get("/", response_class=HTMLResponse)
def holdings_page():
    try:
        df = portfolio_svc.get_holdings()
        if df.empty:
            df = None
    except Exception as e:
        logger.error("Error fetching holdings: %s", e)
        df = None

    body = tabs_html("holdings")

    if df is None:
        body += '<div class="card"><p class="empty">No holdings found. Make sure the correct Groww account is connected.</p></div>'
    else:
        invested = round((df["qty"] * df["avg_cost"]).sum(), 2)
        current = round((df["qty"] * df["ltp"]).sum(), 2)
        total_pnl = round(df["pnl"].sum(), 2)
        pnl_pct = round(total_pnl / invested * 100, 2) if invested else 0
        pnl_class = "green" if total_pnl >= 0 else "red"

        body += f'''<div class="summary">
          <div class="metric"><div class="metric-label">Invested</div><div class="metric-value">₹{invested:,.0f}</div></div>
          <div class="metric"><div class="metric-label">Current Value</div><div class="metric-value">₹{current:,.0f}</div></div>
          <div class="metric"><div class="metric-label">Total P&L</div><div class="metric-value {pnl_class}">₹{total_pnl:,.0f} ({pnl_pct}%)</div></div>
        </div>
        <div class="card"><table><thead><tr>
          <th>Symbol</th><th>Qty</th><th>Avg Cost</th><th>LTP</th><th>P&L</th><th>P&L %</th>
        </tr></thead><tbody>'''
        for _, row in df.iterrows():
            pc = "green" if row["pnl"] >= 0 else "red"
            body += f'<tr><td><a href="/stock/{row["symbol"]}" style="color:#fff;text-decoration:none"><strong>{row["symbol"]}</strong></a></td><td>{row["qty"]}</td><td>₹{row["avg_cost"]:.2f}</td><td>₹{row["ltp"]:.2f}</td><td class="{pc}">₹{row["pnl"]:.0f}</td><td class="{pc}">{row["pnl_pct"]}%</td></tr>'
        body += "</tbody></table></div>"

    return HTML_HEAD + body + HTML_FOOT


@app.get("/signals", response_class=HTMLResponse)
def signals_page():
    try:
        signals = scanner.scan()
    except Exception as e:
        logger.error("Error scanning signals: %s", e)
        signals = []

    body = tabs_html("signals")

    if not signals:
        body += '<div class="card"><p class="empty">No buy signals found at this time. Market conditions may not meet criteria.</p></div>'
    else:
        body += '''<div class="card"><table><thead><tr>
          <th>Symbol</th><th>Sector</th><th>Signal</th><th>Entry</th><th>Target (+8%)</th><th>Stop Loss (-4%)</th><th>RSI</th><th>Volume</th>
        </tr></thead><tbody>'''
        for s in signals:
            badge = "badge-gold" if s.signal_type in ("golden_cross", "supertrend") else "badge-rsi"
            labels = {"golden_cross": "Golden Cross", "rsi_breakout": "RSI Breakout", "momentum": "Momentum", "supertrend": "Supertrend", "rel_strength": "Outperformer", "volume_spike": "Vol Spike"}
            label = labels.get(s.signal_type, s.signal_type)
            body += f'<tr><td><a href="/stock/{s.symbol}" style="color:#fff;text-decoration:none"><strong>{s.symbol}</strong></a></td><td>{s.sector}</td><td><span class="badge {badge}">{label}</span></td><td>₹{s.entry_price:,.2f}</td><td class="green">₹{s.target:,.2f}</td><td class="red">₹{s.stop_loss:,.2f}</td><td class="blue">{s.rsi}</td><td>📈 {s.volume_trend}</td></tr>'
        body += "</tbody></table></div>"

    return HTML_HEAD + body + HTML_FOOT


@app.get("/alerts", response_class=HTMLResponse)
def alerts_page():
    try:
        triggered = alerts_engine.check_and_alert()
    except Exception as e:
        logger.error("Error checking alerts: %s", e)
        triggered = []

    body = tabs_html("alerts")

    if not triggered:
        body += '<div class="card"><p class="empty">✅ No alerts. Your portfolio looks stable.</p></div>'
    else:
        body += '''<div class="card"><table><thead><tr>
          <th>Type</th><th>Symbol</th><th>Details</th>
        </tr></thead><tbody>'''
        for a in triggered:
            if a["type"] == "price_drop":
                badge = '<span class="badge badge-gold">Price Drop</span>'
                detail = f'P&L: <span class="red">{a["pnl_pct"]}%</span> | LTP: ₹{a["ltp"]:.2f} | Avg: ₹{a["avg_cost"]:.2f}'
            else:
                badge = '<span class="badge badge-rsi">Bearish News</span>'
                headlines = "<br>".join(f"• {h[:60]}" for h in a.get("headlines", [])[:3])
                detail = f'Score: <span class="red">{a["sentiment_score"]}</span><br>{headlines}'
            body += f'<tr><td>{badge}</td><td><strong>{a["symbol"]}</strong></td><td>{detail}</td></tr>'
        body += "</tbody></table></div>"

    return HTML_HEAD + body + HTML_FOOT


@app.get("/stock/{symbol}", response_class=HTMLResponse)
def stock_detail(symbol: str):
    import yfinance as yf
    import ta as ta_lib
    from groww_dashboard.services.buy_signals import supertrend

    def tip(label, explanation):
        return f'{label} <span class="info" onclick="this.classList.toggle(\'active\')">i<span class="tooltip">{explanation}</span></span>'

    body = f'<a href="/" class="tab" style="margin-bottom:16px;display:inline-block">← Back</a>'
    body += f'<h1 style="margin-bottom:16px">{symbol}</h1>'

    ticker_str = f"{symbol}.NS"
    stock = yf.Ticker(ticker_str)

    # === FUNDAMENTALS ===
    try:
        info = stock.info
        pe = info.get("trailingPE") or info.get("forwardPE") or "N/A"
        mcap = info.get("marketCap", 0)
        mcap_str = f"₹{mcap/1e7:.0f} Cr" if mcap else "N/A"
        eps = info.get("trailingEps", "N/A")
        div_yield = info.get("dividendYield")
        div_str = f"{div_yield*100:.1f}%" if div_yield else "0%"
        pb = info.get("priceToBook", "N/A")
        bv = info.get("bookValue", "N/A")
        sector = info.get("sector", "N/A")
        industry = info.get("industry", "N/A")

        body += f'<div class="card"><h2 style="margin-bottom:12px;font-size:1rem">🏢 Fundamentals</h2>'
        body += f'<p style="color:#888;margin-bottom:12px">{sector} • {industry}</p>'
        body += '<div class="summary">'
        pe_val = f"{pe:.1f}" if isinstance(pe, (int, float)) else pe
        body += f'<div class="metric"><div class="metric-label">{tip("P/E Ratio", "Price-to-Earnings. Lower = cheaper. Compare within same sector. Below 20 is generally good.")}</div><div class="metric-value">{pe_val}</div></div>'
        body += f'<div class="metric"><div class="metric-label">{tip("Market Cap", "Total company value. Large cap > ₹20,000 Cr. Mid cap ₹5,000-20,000 Cr. Small cap < ₹5,000 Cr.")}</div><div class="metric-value">{mcap_str}</div></div>'
        eps_val = f"₹{eps:.1f}" if isinstance(eps, (int, float)) else eps
        body += f'<div class="metric"><div class="metric-label">{tip("EPS", "Earnings Per Share. Higher = more profitable. Should grow year over year.")}</div><div class="metric-value">{eps_val}</div></div>'
        body += f'<div class="metric"><div class="metric-label">{tip("Dividend Yield", "Annual dividend as % of price. Higher = more passive income. Above 2% is good.")}</div><div class="metric-value green">{div_str}</div></div>'
        pb_val = f"{pb:.2f}" if isinstance(pb, (int, float)) else pb
        body += f'<div class="metric"><div class="metric-label">{tip("P/B Ratio", "Price-to-Book. Below 1 = trading below asset value (undervalued). Above 3 = expensive.")}</div><div class="metric-value">{pb_val}</div></div>'
        bv_val = f"₹{bv:.1f}" if isinstance(bv, (int, float)) else bv
        body += f'<div class="metric"><div class="metric-label">{tip("Book Value", "Net asset value per share. If price < book value, stock may be undervalued.")}</div><div class="metric-value">{bv_val}</div></div>'
        body += '</div></div>'
    except Exception as e:
        logger.debug("Fundamentals error for %s: %s", symbol, e)

    # === PRICE DATA ===
    try:
        df = yf.download(ticker_str, period="1y", progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
    except Exception:
        df = pd.DataFrame()

    if not df.empty:
        close = df["Close"]
        high = df["High"]
        low = df["Low"]

        # === MULTI-TIMEFRAME RETURNS ===
        body += f'<div class="card"><h2 style="margin-bottom:12px;font-size:1rem">📊 {tip("Performance", "Returns over different time periods. Green = profit, Red = loss. Compare with Nifty 50 returns.")}</h2><div class="summary">'
        periods = {"1W": 5, "1M": 21, "3M": 63, "6M": 126, "1Y": 252}
        for label, days in periods.items():
            if len(close) > days:
                ret = ((close.iloc[-1] / close.iloc[-days-1]) - 1) * 100
                c = "green" if ret >= 0 else "red"
                body += f'<div class="metric"><div class="metric-label">{label} Return</div><div class="metric-value {c}">{ret:.1f}%</div></div>'
        body += '</div></div>'

        # === TECHNICAL INDICATORS ===
        rsi = ta_lib.momentum.rsi(close, window=14)
        macd_line = ta_lib.trend.macd(close)
        macd_signal = ta_lib.trend.macd_signal(close)
        sma50 = ta_lib.trend.sma_indicator(close, window=50)
        sma200 = ta_lib.trend.sma_indicator(close, window=200)
        atr = ta_lib.volatility.average_true_range(high, low, close, window=14)
        st_val, st_dir = supertrend(high, low, close)

        latest_rsi = float(rsi.iloc[-1])
        rsi_class = "green" if 40 <= latest_rsi <= 60 else "red" if latest_rsi > 70 or latest_rsi < 30 else "blue"
        st_label = "🟢 Bullish" if st_dir.iloc[-1] == 1 else "🔴 Bearish"
        macd_status = "🟢 Bullish" if macd_line.iloc[-1] > macd_signal.iloc[-1] else "🔴 Bearish"
        sma_status = "🟢 Above" if close.iloc[-1] > sma50.iloc[-1] > sma200.iloc[-1] else "🔴 Below" if close.iloc[-1] < sma200.iloc[-1] else "🟡 Mixed"

        body += '<div class="card"><h2 style="margin-bottom:12px;font-size:1rem">⚡ Technical Indicators</h2><div class="summary">'
        body += f'<div class="metric"><div class="metric-label">{tip("RSI (14)", "Relative Strength Index. Above 70 = overbought (may fall). Below 30 = oversold (may rise). 40-60 = neutral.")}</div><div class="metric-value {rsi_class}">{latest_rsi:.1f}</div></div>'
        body += f'<div class="metric"><div class="metric-label">{tip("Supertrend", "Trend-following indicator. Bullish = price above support line (buy). Bearish = price below resistance (avoid).")}</div><div class="metric-value">{st_label}</div></div>'
        body += f'<div class="metric"><div class="metric-label">{tip("MACD", "Moving Average Convergence Divergence. Bullish = MACD above signal line (momentum up). Bearish = below.")}</div><div class="metric-value">{macd_status}</div></div>'
        body += f'<div class="metric"><div class="metric-label">{tip("SMA 50/200", "Price vs moving averages. Above both = strong uptrend. Below both = downtrend. Mixed = no clear trend.")}</div><div class="metric-value">{sma_status}</div></div>'
        body += f'<div class="metric"><div class="metric-label">{tip("ATR", "Average True Range. Measures daily volatility in ₹. Higher = more volatile/risky. Use for stop-loss sizing.")}</div><div class="metric-value">₹{float(atr.iloc[-1]):.1f}</div></div>'
        body += f'<div class="metric"><div class="metric-label">{tip("50 SMA", "50-day Simple Moving Average. Acts as support in uptrend. If price crosses below, trend may be weakening.")}</div><div class="metric-value">₹{float(sma50.iloc[-1]):.1f}</div></div>'
        body += '</div>'

        # Support / Resistance
        recent_high = float(high.iloc[-20:].max())
        recent_low = float(low.iloc[-20:].min())
        pivot = (recent_high + recent_low + float(close.iloc[-1])) / 3
        r1 = 2 * pivot - recent_low
        s1 = 2 * pivot - recent_high
        body += f'<div class="summary" style="margin-top:12px">'
        body += f'<div class="metric"><div class="metric-label">{tip("Support (S1)", "Price level where buying interest is strong. Stock tends to bounce here. Good entry point.")}</div><div class="metric-value green">₹{s1:.1f}</div></div>'
        body += f'<div class="metric"><div class="metric-label">{tip("Pivot", "Central price level for the day. Above pivot = bullish bias. Below = bearish bias.")}</div><div class="metric-value">₹{pivot:.1f}</div></div>'
        body += f'<div class="metric"><div class="metric-label">{tip("Resistance (R1)", "Price level where selling pressure is strong. Stock struggles to go above. Consider booking profits here.")}</div><div class="metric-value red">₹{r1:.1f}</div></div>'
        body += '</div></div>'

        # === RISK ===
        try:
            nifty = yf.download("^NSEI", period="1y", progress=False, auto_adjust=True)
            if isinstance(nifty.columns, pd.MultiIndex):
                nifty.columns = nifty.columns.get_level_values(0)
            stock_ret = close.pct_change().dropna()
            nifty_ret = nifty["Close"].pct_change().dropna()
            common = stock_ret.index.intersection(nifty_ret.index)
            if len(common) > 50:
                import numpy as np
                sr = stock_ret.loc[common]
                nr = nifty_ret.loc[common]
                beta = float(np.cov(sr, nr)[0][1] / np.var(nr))
                volatility = float(sr.std() * np.sqrt(252) * 100)
                body += '<div class="card"><h2 style="margin-bottom:12px;font-size:1rem">⚠️ Risk</h2><div class="summary">'
                beta_class = "green" if beta < 1 else "red"
                body += f'<div class="metric"><div class="metric-label">{tip("Beta", "Measures stock movement vs Nifty. Beta 1 = moves with market. Above 1 = more volatile. Below 1 = defensive.")}</div><div class="metric-value {beta_class}">{beta:.2f}</div></div>'
                body += f'<div class="metric"><div class="metric-label">{tip("Annual Volatility", "How much price swings annually. Below 25% = low risk. 25-40% = moderate. Above 40% = high risk.")}</div><div class="metric-value">{volatility:.1f}%</div></div>'
                body += f'<div class="metric"><div class="metric-label">{tip("52W High", "Highest price in the last year. How far current price is from it shows potential upside.")}</div><div class="metric-value green">₹{float(close.max()):.1f}</div></div>'
                body += f'<div class="metric"><div class="metric-label">{tip("52W Low", "Lowest price in the last year. How far current price is from it shows downside risk.")}</div><div class="metric-value red">₹{float(close.min()):.1f}</div></div>'
                body += '</div></div>'
        except Exception:
            pass

        # === PRICE HISTORY TABLE ===
        recent = df.tail(20)[["Open", "High", "Low", "Close", "Volume"]].round(2).reset_index()
        recent["Date"] = recent["Date"].dt.strftime("%d %b %Y")
        body += '<div class="card"><h2 style="margin-bottom:12px;font-size:1rem">📈 Price History (Last 20 Days)</h2>'
        body += '<table><thead><tr><th>Date</th><th>Open</th><th>High</th><th>Low</th><th>Close</th><th>Volume</th></tr></thead><tbody>'
        for _, r in recent.iterrows():
            body += f'<tr><td>{r["Date"]}</td><td>₹{r["Open"]:.2f}</td><td>₹{r["High"]:.2f}</td><td>₹{r["Low"]:.2f}</td><td>₹{r["Close"]:.2f}</td><td>{int(r["Volume"]):,}</td></tr>'
        body += '</tbody></table></div>'
    else:
        body += '<div class="card"><p class="empty">No price data found.</p></div>'

    # === OWNERSHIP ===
    try:
        holders = stock.major_holders
        if holders is not None and not holders.empty:
            body += f'<div class="card"><h2 style="margin-bottom:12px;font-size:1rem">👥 {tip("Ownership", "Shows who owns the company. High promoter holding (>50%) = good confidence. Rising FII = institutional interest.")}</h2>'
            body += '<table><thead><tr><th>%</th><th>Holder Type</th></tr></thead><tbody>'
            for _, row in holders.iterrows():
                body += f'<tr><td><strong>{row.iloc[0]}</strong></td><td>{row.iloc[1]}</td></tr>'
            body += '</tbody></table></div>'
    except Exception:
        pass

    # === NEWS ===
    try:
        articles = news_svc.get_sentiment(symbol, max_articles=10)
        if articles:
            body += '<div class="card"><h2 style="margin-bottom:12px;font-size:1rem">📰 Latest News</h2>'
            body += '<table><thead><tr><th>Headline</th><th>Sentiment</th><th>Link</th></tr></thead><tbody>'
            for a in articles:
                s_class = "green" if a.label == "positive" else "red" if a.label == "negative" else "blue"
                body += f'<tr><td>{a.headline[:80]}</td><td class="{s_class}">{a.label} ({a.sentiment_score:.2f})</td><td><a href="{a.url}" target="_blank" style="color:#3b82f6">Read →</a></td></tr>'
            body += '</tbody></table></div>'
    except Exception:
        pass

    return HTML_HEAD + body + HTML_FOOT


@app.get("/api/holdings")
def api_holdings():
    df = portfolio_svc.get_holdings()
    if df.empty:
        return {"holdings": [], "summary": {}}
    return {"holdings": df.to_dict(orient="records"), "summary": portfolio_svc.summary()}


@app.get("/debug")
def debug():
    import os
    import requests as req
    info = {}
    # Check our outbound IP
    try:
        info["server_ip"] = req.get("https://api.ipify.org", timeout=5).text
    except Exception as e:
        info["server_ip"] = str(e)
    # Check if token is set
    key = os.environ.get("GROWW_API_KEY", "")
    info["token_length"] = len(key)
    info["token_prefix"] = key[:20] + "..." if key else "EMPTY"
    # Try Groww API directly
    try:
        result = groww.get_holdings_for_user()
        info["groww_status"] = "OK"
        info["holdings_count"] = len(result.get("holdings", []))
    except Exception as e:
        info["groww_status"] = f"ERROR: {e}"
    return info


@app.get("/api/signals")
def api_signals():
    signals = scanner.scan()
    return {"signals": [s.__dict__ for s in signals]}


@app.get("/api/search")
def api_search(q: str = ""):
    """Search NSE stocks by symbol or name."""
    import yfinance as yf

    q = q.strip().upper()
    if len(q) < 2:
        return {"results": []}

    # Try direct symbol match first
    results = []
    candidates = [q, q.replace(" ", "")]

    for sym in candidates:
        ticker = yf.Ticker(f"{sym}.NS")
        try:
            info = ticker.info
            if info.get("symbol") or info.get("shortName"):
                results.append({
                    "symbol": sym,
                    "name": info.get("shortName", info.get("longName", sym)),
                })
                break
        except Exception:
            continue

    # Also check holdings for local matches
    try:
        df = portfolio_svc.get_holdings()
        if not df.empty:
            matches = df[df["symbol"].str.contains(q, case=False, na=False)]
            for _, row in matches.iterrows():
                if not any(r["symbol"] == row["symbol"] for r in results):
                    results.append({"symbol": row["symbol"], "name": row["symbol"]})
    except Exception:
        pass

    return {"results": results[:10]}
