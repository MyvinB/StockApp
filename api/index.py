"""Vercel serverless API — Groww portfolio dashboard."""

import os

import pandas as pd
import pyotp
import redis
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from growwapi import GrowwAPI

load_dotenv()

app = FastAPI()

TOTP_TOKEN = os.environ["GROWW_TOTP_TOKEN"]
TOTP_SECRET = os.environ["GROWW_TOTP_SECRET"]
REDIS_URL = os.environ["UPSTASH_REDIS_URL"]

r = redis.from_url(REDIS_URL)


def get_groww() -> GrowwAPI:
    token = r.get("groww_access_token")
    if not token:
        # Auto-generate via TOTP
        totp = pyotp.TOTP(TOTP_SECRET).now()
        access_token = GrowwAPI.get_access_token(api_key=TOTP_TOKEN, totp=totp)
        r.setex("groww_access_token", 12 * 3600, access_token)
        token = access_token.encode()
    return GrowwAPI(token.decode() if isinstance(token, bytes) else token)


@app.get("/holdings")
def holdings():
    groww = get_groww()
    response = groww.get_holdings_for_user()
    raw = response.get("holdings", [])

    if not raw:
        return {"holdings": [], "summary": {}}

    df = pd.DataFrame(raw)
    df = df.rename(columns={
        "trading_symbol": "symbol", "quantity": "qty", "average_price": "avg_cost",
    })[["symbol", "qty", "avg_cost"]]

    symbols = tuple(f"NSE_{s}" for s in df["symbol"])
    ltp_data = groww.get_ltp(segment=groww.SEGMENT_CASH, exchange_trading_symbols=symbols)
    df["ltp"] = df["symbol"].map(lambda s: ltp_data.get(f"NSE_{s}", 0))
    df["current_value"] = df["qty"] * df["ltp"]
    df["invested_value"] = df["qty"] * df["avg_cost"]
    df["pnl"] = df["current_value"] - df["invested_value"]
    df["pnl_pct"] = ((df["ltp"] - df["avg_cost"]) / df["avg_cost"] * 100).round(2)

    return {
        "holdings": df.to_dict(orient="records"),
        "summary": {
            "total_invested": round(df["invested_value"].sum(), 2),
            "current_value": round(df["current_value"].sum(), 2),
            "total_pnl": round(df["pnl"].sum(), 2),
        },
    }
