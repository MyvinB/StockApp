"""Portfolio ingestion: fetch Groww holdings + LTP, transform to DataFrame."""

import logging

import pandas as pd
from growwapi import GrowwAPI

from groww_dashboard.services.session_manager import SessionManager

logger = logging.getLogger(__name__)


class PortfolioService:
    """Fetches and transforms Groww holdings into structured data."""

    def __init__(self, groww: GrowwAPI, session_manager: SessionManager = None):
        self._groww = groww
        self._session_manager = session_manager

    def get_holdings(self) -> pd.DataFrame:
        """Fetch holdings, enrich with LTP, compute P&L."""
        import time

        response = None
        for attempt in range(3):
            try:
                response = self._groww.get_holdings_for_user()
                break
            except Exception as e:
                logger.warning("Holdings attempt %d: type=%s, msg='%s'", attempt + 1, type(e).__name__, e)
                err_str = str(e).lower()
                if ("forbidden" in err_str or "authoris" in err_str) and attempt < 2:
                    time.sleep(2 * (attempt + 1))
                else:
                    raise
        if response is None:
            return pd.DataFrame()
        logger.debug("Groww raw response: %s", str(response)[:500])

        holdings = self._extract_holdings(response)

        # Retry with refreshed session if empty (possible token expiry)
        if not holdings and self._session_manager:
            logger.info("Holdings empty, refreshing session...")
            self._groww = self._session_manager.refresh()
            response = self._groww.get_holdings_for_user()
            holdings = self._extract_holdings(response)

        if not holdings:
            logger.warning("No holdings found. Response: %s", str(response)[:300])
            return pd.DataFrame()

        df = pd.DataFrame(holdings)
        logger.debug("Holdings columns: %s", list(df.columns))

        df = df.rename(columns={
            "trading_symbol": "symbol",
            "tradingSymbol": "symbol",
            "quantity": "qty",
            "average_price": "avg_cost",
            "averagePrice": "avg_cost",
        })

        required = {"symbol", "qty", "avg_cost"}
        if not required.issubset(df.columns):
            logger.error("Missing columns. Have: %s, Need: %s", list(df.columns), required)
            return pd.DataFrame()

        df = df[["symbol", "qty", "avg_cost"]].copy()
        df["qty"] = pd.to_numeric(df["qty"], errors="coerce").fillna(0)
        df["avg_cost"] = pd.to_numeric(df["avg_cost"], errors="coerce").fillna(0)

        # Fetch LTP for all symbols
        symbols = tuple(f"NSE_{s}" for s in df["symbol"])
        try:
            ltp_data = self._groww.get_ltp(
                segment=self._groww.SEGMENT_CASH,
                exchange_trading_symbols=symbols,
            )
        except Exception as e:
            logger.warning("Groww LTP unavailable (%s), falling back to yfinance...", e)
            ltp_data = self._fallback_ltp(df["symbol"].tolist())
        df["ltp"] = df["symbol"].map(lambda s: ltp_data.get(f"NSE_{s}", ltp_data.get(s, 0)))

        # Warn about symbols with no LTP (possibly delisted or symbol changed)
        zero_ltp = df[df["ltp"] == 0]["symbol"].tolist()
        if zero_ltp:
            logger.warning("No LTP for symbols (may be delisted/renamed): %s", zero_ltp)

        df["current_value"] = df["qty"] * df["ltp"]
        df["invested_value"] = df["qty"] * df["avg_cost"]
        df["pnl"] = df["current_value"] - df["invested_value"]
        df["pnl_pct"] = ((df["ltp"] - df["avg_cost"]) / df["avg_cost"] * 100).round(2)
        # Mark symbols with no LTP as NaN P&L instead of -100%
        df.loc[df["ltp"] == 0, ["pnl", "pnl_pct"]] = 0
        return df

    @staticmethod
    def _fallback_ltp(symbols: list) -> dict:
        """Fetch last closing prices from yfinance as LTP fallback."""
        import yfinance as yf
        tickers = " ".join(f"{s}.NS" for s in symbols)
        try:
            data = yf.download(tickers, period="1d", progress=False, auto_adjust=True)
            if data.empty:
                return {}
            if isinstance(data.columns, pd.MultiIndex):
                close = data["Close"].iloc[-1]
                return {f"NSE_{s}": float(close.get(f"{s}.NS", 0) or 0) for s in symbols}
            else:
                price = float(data["Close"].iloc[-1]) if len(symbols) == 1 else 0
                return {f"NSE_{symbols[0]}": price} if len(symbols) == 1 else {}
        except Exception as e:
            logger.error("yfinance fallback failed: %s", e)
            return {}

    @staticmethod
    def _extract_holdings(response) -> list:
        if isinstance(response, list):
            return response
        if isinstance(response, dict):
            return response.get("holdings") or response.get("data", {}).get("holdings", [])
        return []

    def summary(self) -> dict:
        """Return portfolio-level aggregates."""
        df = self.get_holdings()
        if df.empty:
            return {"total_invested": 0, "current_value": 0, "total_pnl": 0, "pnl_pct": 0}
        return {
            "total_invested": round(df["invested_value"].sum(), 2),
            "current_value": round(df["current_value"].sum(), 2),
            "total_pnl": round(df["pnl"].sum(), 2),
            "pnl_pct": round(df["pnl"].sum() / df["invested_value"].sum() * 100, 2),
        }
