"""Buy Signals Scanner: Sector momentum + multi-strategy stock selection."""

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
import ta as ta_lib
import yfinance as yf

logger = logging.getLogger(__name__)

NIFTY_TICKER = "^NSEI"

SECTOR_INDICES = {
    "Nifty IT": "^CNXIT",
    "Nifty Bank": "^NSEBANK",
    "Nifty Auto": "^CNXAUTO",
    "Nifty Pharma": "^CNXPHARMA",
    "Nifty FMCG": "^CNXFMCG",
    "Nifty Metal": "^CNXMETAL",
    "Nifty Realty": "^CNXREALTY",
    "Nifty Energy": "^CNXENERGY",
    "Nifty Infra": "^CNXINFRA",
    "Nifty PSE": "^CNXPSE",
}

SECTOR_STOCKS = {
    "Nifty IT": ["TCS.NS", "INFY.NS", "WIPRO.NS", "HCLTECH.NS", "TECHM.NS", "LTIMindtree.NS", "MPHASIS.NS", "COFORGE.NS"],
    "Nifty Bank": ["HDFCBANK.NS", "ICICIBANK.NS", "KOTAKBANK.NS", "AXISBANK.NS", "SBIN.NS", "INDUSINDBK.NS", "BANKBARODA.NS", "PNB.NS"],
    "Nifty Auto": ["TATAMOTORS.NS", "M&M.NS", "MARUTI.NS", "BAJAJ-AUTO.NS", "HEROMOTOCO.NS", "EICHERMOT.NS", "ASHOKLEY.NS", "TVSMOTOR.NS"],
    "Nifty Pharma": ["SUNPHARMA.NS", "DRREDDY.NS", "CIPLA.NS", "DIVISLAB.NS", "APOLLOHOSP.NS", "LUPIN.NS", "AUROPHARMA.NS", "BIOCON.NS"],
    "Nifty FMCG": ["HINDUNILVR.NS", "ITC.NS", "NESTLEIND.NS", "BRITANNIA.NS", "DABUR.NS", "GODREJCP.NS", "MARICO.NS", "COLPAL.NS"],
    "Nifty Metal": ["TATASTEEL.NS", "JSWSTEEL.NS", "HINDALCO.NS", "VEDL.NS", "COALINDIA.NS", "NMDC.NS", "SAIL.NS", "NATIONALUM.NS"],
    "Nifty Realty": ["DLF.NS", "GODREJPROP.NS", "OBEROIRLTY.NS", "PHOENIXLTD.NS", "PRESTIGE.NS", "BRIGADE.NS", "SOBHA.NS"],
    "Nifty Energy": ["RELIANCE.NS", "ONGC.NS", "NTPC.NS", "POWERGRID.NS", "ADANIGREEN.NS", "TATAPOWER.NS", "BPCL.NS", "IOC.NS"],
    "Nifty Infra": ["LARSEN.NS", "ADANIENT.NS", "ULTRACEMCO.NS", "GRASIM.NS", "ADANIPORTS.NS", "SIEMENS.NS", "ABB.NS"],
    "Nifty PSE": ["SBIN.NS", "ONGC.NS", "NTPC.NS", "COALINDIA.NS", "BPCL.NS", "IOC.NS", "BHEL.NS", "BEL.NS"],
}


@dataclass
class BuySignal:
    symbol: str
    sector: str
    entry_price: float
    target: float
    stop_loss: float
    signal_type: str
    rsi: float
    volume_trend: str


def supertrend(high, low, close, period=10, multiplier=3):
    """Calculate Supertrend indicator."""
    atr = ta_lib.volatility.average_true_range(high, low, close, window=period)
    hl2 = (high + low) / 2
    upper_band = hl2 + (multiplier * atr)
    lower_band = hl2 - (multiplier * atr)

    st = pd.Series(index=close.index, dtype=float)
    direction = pd.Series(index=close.index, dtype=int)
    st.iloc[0] = upper_band.iloc[0]
    direction.iloc[0] = 1

    for i in range(1, len(close)):
        if close.iloc[i] > upper_band.iloc[i - 1]:
            direction.iloc[i] = 1
        elif close.iloc[i] < lower_band.iloc[i - 1]:
            direction.iloc[i] = -1
        else:
            direction.iloc[i] = direction.iloc[i - 1]

        if direction.iloc[i] == 1:
            st.iloc[i] = max(lower_band.iloc[i], st.iloc[i - 1]) if direction.iloc[i - 1] == 1 else lower_band.iloc[i]
        else:
            st.iloc[i] = min(upper_band.iloc[i], st.iloc[i - 1]) if direction.iloc[i - 1] == -1 else upper_band.iloc[i]

    return st, direction


class BuySignalScanner:
    """Multi-strategy screener: sector momentum → stock selection."""

    def __init__(self, period: str = "1y"):
        self._period = period
        self._nifty_returns = None

    def scan(self) -> list[BuySignal]:
        """Run full scan and return buy signals."""
        logger.info("Step 1: Scanning sector momentum...")
        self._load_nifty_returns()
        top_sectors = self._get_top_sectors(top_n=5)
        logger.info("Top sectors: %s", [s[0] for s in top_sectors])

        logger.info("Step 2: Scanning individual stocks...")
        signals = []
        for sector_name, _ in top_sectors:
            stocks = SECTOR_STOCKS.get(sector_name, [])
            sector_signals = self._scan_stocks(stocks, sector_name)
            signals.extend(sector_signals)

        logger.info("Found %d buy signals.", len(signals))
        return signals

    def _load_nifty_returns(self):
        """Load Nifty 50 returns for relative strength comparison."""
        try:
            df = yf.download(NIFTY_TICKER, period=self._period, progress=False, auto_adjust=True)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            self._nifty_returns = df["Close"].pct_change()
        except Exception:
            self._nifty_returns = None

    def _get_top_sectors(self, top_n: int = 5) -> list[tuple[str, float]]:
        """Identify sectors with strong momentum."""
        scored = []
        for name, ticker in SECTOR_INDICES.items():
            try:
                df = yf.download(ticker, period=self._period, progress=False, auto_adjust=True)
                if df.empty or len(df) < 50:
                    continue
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                close = df["Close"]
                ema50 = ta_lib.trend.ema_indicator(close, window=50)
                rsi = ta_lib.momentum.rsi(close, window=14)
                latest_close = close.iloc[-1]
                latest_ema = ema50.iloc[-1]
                latest_rsi = rsi.iloc[-1]

                if latest_close > latest_ema and 45 <= latest_rsi <= 75:
                    score = ((latest_close - latest_ema) / latest_ema * 100) + latest_rsi
                    scored.append((name, score))
            except Exception:
                continue

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_n]

    def _scan_stocks(self, tickers: list[str], sector: str) -> list[BuySignal]:
        """Multi-strategy stock scan."""
        signals = []
        for ticker in tickers:
            try:
                df = yf.download(ticker, period=self._period, progress=False, auto_adjust=True)
                if df.empty or len(df) < 200:
                    continue
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)

                close = df["Close"]
                high = df["High"]
                low = df["Low"]
                volume = df["Volume"]

                sma50 = ta_lib.trend.sma_indicator(close, window=50)
                sma200 = ta_lib.trend.sma_indicator(close, window=200)
                rsi = ta_lib.momentum.rsi(close, window=14)

                latest_close = float(close.iloc[-1])
                latest_rsi = float(rsi.iloc[-1])

                signal_type = None

                # 1. Supertrend buy: direction just flipped to bullish
                st, direction = supertrend(high, low, close)
                if direction.iloc[-1] == 1 and direction.iloc[-3] == -1:
                    signal_type = "supertrend"

                # 2. Golden cross: 50 SMA crossed above 200 SMA in last 10 days
                elif sma50.iloc[-1] > sma200.iloc[-1] and sma50.iloc[-11] <= sma200.iloc[-11]:
                    signal_type = "golden_cross"

                # 3. Relative Strength vs Nifty: stock outperforming over 20 days
                elif self._nifty_returns is not None:
                    stock_ret_20d = (close.iloc[-1] / close.iloc[-21] - 1) * 100
                    nifty_ret_20d = (self._nifty_returns.iloc[-20:].sum()) * 100
                    if stock_ret_20d > nifty_ret_20d + 5 and latest_rsi > 55:
                        signal_type = "rel_strength"

                # 4. Volume spike (delivery proxy): volume 2x above 20-day avg
                if not signal_type:
                    vol_20_avg = volume.iloc[-21:-1].mean()
                    if volume.iloc[-1] > vol_20_avg * 2 and latest_close > float(sma50.iloc[-1]):
                        signal_type = "volume_spike"

                # 5. RSI breakout
                if not signal_type and latest_rsi > 55 and float(rsi.iloc[-5]) < 50:
                    signal_type = "rsi_breakout"

                # 6. Momentum: price above both SMAs + RSI strong
                if not signal_type and latest_close > float(sma50.iloc[-1]) > float(sma200.iloc[-1]) and latest_rsi > 60:
                    signal_type = "momentum"

                if signal_type:
                    # Dynamic stop-loss using ATR
                    atr = ta_lib.volatility.average_true_range(high, low, close, window=14)
                    atr_val = float(atr.iloc[-1])
                    stop_loss = round(latest_close - (2 * atr_val), 2)
                    target = round(latest_close + (3 * atr_val), 2)  # 1.5:1 risk-reward

                    vol_5d = volume.iloc[-5:]
                    vol_trend = "rising" if vol_5d.iloc[-1] > vol_5d.mean() else "flat"

                    symbol = ticker.replace(".NS", "")
                    signals.append(BuySignal(
                        symbol=symbol,
                        sector=sector,
                        entry_price=round(latest_close, 2),
                        target=target,
                        stop_loss=stop_loss,
                        signal_type=signal_type,
                        rsi=round(latest_rsi, 1),
                        volume_trend=vol_trend,
                    ))
            except Exception as e:
                logger.debug("Skipping %s: %s", ticker, e)
                continue
        return signals

    def scan_as_df(self) -> pd.DataFrame:
        signals = self.scan()
        if not signals:
            return pd.DataFrame()
        return pd.DataFrame([s.__dict__ for s in signals])
