"""News sentiment analysis using Google News RSS + VADER."""

import logging
from dataclasses import dataclass
from xml.etree import ElementTree

import requests
from nltk.sentiment.vader import SentimentIntensityAnalyzer

logger = logging.getLogger(__name__)


@dataclass
class NewsSentiment:
    symbol: str
    headline: str
    sentiment_score: float  # -1 (bearish) to +1 (bullish)
    label: str  # "negative", "neutral", "positive"
    url: str


class NewsSentimentService:
    """Fetches stock news from Google News RSS and scores sentiment."""

    GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}+stock+NSE&hl=en-IN&gl=IN&ceid=IN:en"

    def __init__(self):
        self._sia = SentimentIntensityAnalyzer()

    def get_sentiment(self, symbol: str, max_articles: int = 10) -> list[NewsSentiment]:
        """Fetch recent news and return sentiment scores for a stock."""
        url = self.GOOGLE_NEWS_RSS.format(query=symbol)
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.error("Failed to fetch news for %s: %s", symbol, e)
            return []

        results = []
        root = ElementTree.fromstring(resp.content)
        items = root.findall(".//item")[:max_articles]

        for item in items:
            title = item.findtext("title", "")
            link = item.findtext("link", "")
            score = self._sia.polarity_scores(title)["compound"]
            label = "negative" if score <= -0.2 else "positive" if score >= 0.2 else "neutral"
            results.append(NewsSentiment(
                symbol=symbol, headline=title,
                sentiment_score=score, label=label, url=link,
            ))
        return results

    def get_overall_sentiment(self, symbol: str) -> float:
        """Return average sentiment score for a symbol. <0 = bearish."""
        articles = self.get_sentiment(symbol)
        if not articles:
            return 0.0
        return sum(a.sentiment_score for a in articles) / len(articles)

    def get_bearish_alerts(self, symbols: list[str], threshold: float = -0.15) -> list[dict]:
        """Return symbols with negative sentiment below threshold."""
        alerts = []
        for sym in symbols:
            score = self.get_overall_sentiment(sym)
            if score < threshold:
                articles = [a for a in self.get_sentiment(sym) if a.label == "negative"]
                alerts.append({
                    "symbol": sym,
                    "sentiment_score": round(score, 3),
                    "negative_headlines": [a.headline for a in articles[:3]],
                })
        return alerts
