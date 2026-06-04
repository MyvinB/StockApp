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
        try:
            response = self._groww.get_holdings_for_user()
        except Exception as e:
            if self._session_manager and "forbidden" in str(e).lower():
                logger.info("Token expired (forbidden), refreshing session...")
                self._groww = self._session_manager.refresh()
                response = self._groww.get_holdings_for_user()
            else:
                raise
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
        ltp_data = self._groww.get_ltp(
            segment=self._groww.SEGMENT_CASH,
            exchange_trading_symbols=symbols,
        )
        df["ltp"] = df["symbol"].map(lambda s: ltp_data.get(f"NSE_{s}", 0))

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
