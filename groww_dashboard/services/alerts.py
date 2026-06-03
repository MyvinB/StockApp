"""Alerts engine: monitors portfolio for price drops + negative news."""

import logging

from growwapi import GrowwAPI

from groww_dashboard.services.news_sentiment import NewsSentimentService
from groww_dashboard.services.notifications import NotificationService
from groww_dashboard.services.portfolio import PortfolioService

logger = logging.getLogger(__name__)


class AlertsEngine:
    """Checks holdings for price drops and bearish sentiment, sends notifications."""

    def __init__(self, groww: GrowwAPI, drop_threshold: float = -3.0, sentiment_threshold: float = -0.15):
        self._portfolio = PortfolioService(groww)
        self._news = NewsSentimentService()
        self._notifier = NotificationService()
        self._drop_threshold = drop_threshold  # P&L % trigger
        self._sentiment_threshold = sentiment_threshold

    def check_and_alert(self) -> list[dict]:
        """Run all checks and send alerts. Returns list of triggered alerts."""
        triggered = []

        df = self._portfolio.get_holdings()
        if df.empty:
            logger.info("No holdings to monitor.")
            return triggered

        # Check 1: Price drop alerts
        dropping = df[df["pnl_pct"] <= self._drop_threshold]
        for _, row in dropping.iterrows():
            alert = {
                "type": "price_drop",
                "symbol": row["symbol"],
                "pnl_pct": row["pnl_pct"],
                "ltp": row["ltp"],
                "avg_cost": row["avg_cost"],
            }
            triggered.append(alert)
            self._notifier.alert(
                subject=f"⚠️ {row['symbol']} down {row['pnl_pct']}%",
                body=f"{row['symbol']} is at ₹{row['ltp']:.2f} (avg cost ₹{row['avg_cost']:.2f}). P&L: {row['pnl_pct']}%",
            )

        # Check 2: Negative news sentiment
        symbols = df["symbol"].tolist()
        bearish = self._news.get_bearish_alerts(symbols, self._sentiment_threshold)
        for item in bearish:
            alert = {
                "type": "negative_sentiment",
                "symbol": item["symbol"],
                "sentiment_score": item["sentiment_score"],
                "headlines": item["negative_headlines"],
            }
            triggered.append(alert)
            headlines = "\n".join(f"• {h}" for h in item["negative_headlines"])
            self._notifier.alert(
                subject=f"📰 Bearish news for {item['symbol']} (score: {item['sentiment_score']})",
                body=f"Negative sentiment detected:\n{headlines}",
            )

        logger.info("Alert check complete. %d alerts triggered.", len(triggered))
        return triggered
