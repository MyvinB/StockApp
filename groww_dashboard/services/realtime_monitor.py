from __future__ import annotations

"""Real-time price monitoring via Groww WebSocket feed."""

import logging
import threading

import pandas as pd
from growwapi import GrowwAPI, GrowwFeed

from groww_dashboard.services.notifications import NotificationService

logger = logging.getLogger(__name__)

INSTRUMENTS_CSV_URL = "https://growwapi-assets.groww.in/instruments/instrument.csv"


class RealtimeMonitor:
    """Subscribes to live price feed and alerts on threshold breaches."""

    def __init__(self, groww: GrowwAPI, drop_threshold: float = -3.0):
        self._groww = groww
        self._feed = GrowwFeed(groww)
        self._notifier = NotificationService()
        self._drop_threshold = drop_threshold
        self._holdings: dict = {}  # symbol -> {avg_cost, qty, exchange_token}
        self._alerted: set = set()  # avoid repeat alerts
        self._instruments_df: pd.DataFrame | None = None
        self._thread: threading.Thread | None = None
        self._running = False

    def start(self):
        """Load holdings, resolve exchange tokens, subscribe to feed."""
        self._load_instruments()
        self._load_holdings()

        if not self._holdings:
            logger.warning("No holdings to monitor.")
            return

        instruments_list = [
            {"exchange": "NSE", "segment": "CASH", "exchange_token": str(h["exchange_token"])}
            for h in self._holdings.values()
            if h.get("exchange_token")
        ]

        if not instruments_list:
            logger.warning("No exchange tokens resolved. Cannot start feed.")
            return

        self._feed.subscribe_ltp(instruments_list, on_data_received=self._on_price_update)
        self._running = True
        self._thread = threading.Thread(target=self._feed.consume, daemon=True)
        self._thread.start()
        logger.info("Real-time monitor started for %d instruments.", len(instruments_list))

    def stop(self):
        self._running = False

    def _on_price_update(self, meta):
        """Callback fired on each LTP update from WebSocket."""
        ltp_data = self._feed.get_ltp()
        nse_cash = ltp_data.get("ltp", {}).get("NSE", {}).get("CASH", {})

        for symbol, info in self._holdings.items():
            token = str(info.get("exchange_token", ""))
            if token in nse_cash:
                ltp = nse_cash[token].get("ltp", 0)
                if ltp and info["avg_cost"]:
                    pnl_pct = ((ltp - info["avg_cost"]) / info["avg_cost"]) * 100
                    if pnl_pct <= self._drop_threshold and symbol not in self._alerted:
                        self._alerted.add(symbol)
                        self._trigger_alert(symbol, ltp, info["avg_cost"], pnl_pct)

    def _trigger_alert(self, symbol: str, ltp: float, avg_cost: float, pnl_pct: float):
        logger.warning("ALERT: %s dropped %.1f%% (LTP: %.2f, Avg: %.2f)", symbol, pnl_pct, ltp, avg_cost)
        self._notifier.alert(
            subject=f"🚨 {symbol} down {pnl_pct:.1f}%",
            body=f"{symbol} is at ₹{ltp:.2f} (avg ₹{avg_cost:.2f}). Drop: {pnl_pct:.1f}%",
        )

    def _load_holdings(self):
        """Fetch holdings and map to exchange tokens."""
        response = self._groww.get_holdings_for_user()
        holdings = response.get("holdings", [])
        for h in holdings:
            symbol = h.get("trading_symbol", "")
            token = self._resolve_exchange_token(symbol)
            self._holdings[symbol] = {
                "avg_cost": h.get("average_price", 0),
                "qty": h.get("quantity", 0),
                "exchange_token": token,
            }
        logger.info("Loaded %d holdings for monitoring.", len(self._holdings))

    def _load_instruments(self):
        """Download Groww instruments CSV for token mapping."""
        try:
            self._instruments_df = pd.read_csv(INSTRUMENTS_CSV_URL)
            logger.info("Loaded instruments CSV (%d rows).", len(self._instruments_df))
        except Exception as e:
            logger.error("Failed to load instruments CSV: %s", e)
            self._instruments_df = pd.DataFrame()

    def _resolve_exchange_token(self, symbol: str) -> str | None:
        """Map trading symbol to exchange token using instruments CSV."""
        if self._instruments_df is None or self._instruments_df.empty:
            return None
        match = self._instruments_df[
            (self._instruments_df["trading_symbol"] == symbol)
            & (self._instruments_df["exchange"] == "NSE")
            & (self._instruments_df["segment"] == "CASH")
        ]
        if not match.empty:
            return str(int(match.iloc[0]["exchange_token"]))
        return None

    def reset_alerts(self):
        """Clear alerted set to allow re-alerting."""
        self._alerted.clear()
