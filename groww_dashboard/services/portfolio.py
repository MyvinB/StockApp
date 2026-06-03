"""Portfolio ingestion: fetch Groww holdings + LTP, transform to DataFrame."""

import logging

import pandas as pd
from growwapi import GrowwAPI

logger = logging.getLogger(__name__)


class PortfolioService:
    """Fetches and transforms Groww holdings into structured data."""

    def __init__(self, groww: GrowwAPI):
        self._groww = groww

    def get_holdings(self) -> pd.DataFrame:
        """Fetch holdings, enrich with LTP, compute P&L."""
        response = self._groww.get_holdings_for_user()
        holdings = response.get("holdings", [])

        if not holdings:
            logger.warning("No holdings found.")
            return pd.DataFrame()

        df = pd.DataFrame(holdings)
        df = df.rename(columns={
            "trading_symbol": "symbol",
            "quantity": "qty",
            "average_price": "avg_cost",
        })[["symbol", "qty", "avg_cost"]]

        # Fetch LTP for all symbols
        symbols = tuple(f"NSE_{s}" for s in df["symbol"])
        ltp_data = self._groww.get_ltp(
            segment=self._groww.SEGMENT_CASH,
            exchange_trading_symbols=symbols,
        )
        df["ltp"] = df["symbol"].map(lambda s: ltp_data.get(f"NSE_{s}", 0))
        df["current_value"] = df["qty"] * df["ltp"]
        df["invested_value"] = df["qty"] * df["avg_cost"]
        df["pnl"] = df["current_value"] - df["invested_value"]
        df["pnl_pct"] = ((df["ltp"] - df["avg_cost"]) / df["avg_cost"] * 100).round(2)
        return df

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
