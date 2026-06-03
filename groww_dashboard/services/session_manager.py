"""Session management: Groww API authentication with checksum."""

import hashlib
import logging
import time

import requests
from growwapi import GrowwAPI

from groww_dashboard.config import GrowwConfig

logger = logging.getLogger(__name__)


class SessionManager:
    """Handles Groww authentication via API Key + Secret + Checksum."""

    TOKEN_URL = "https://api.groww.in/v1/token/api/access"

    def __init__(self, config: GrowwConfig):
        self._config = config

    def login(self) -> GrowwAPI:
        """Generate access token using checksum flow."""
        # If already a JWT (direct access token), use as-is
        if self._config.api_key.startswith("eyJ"):
            groww = GrowwAPI(self._config.api_key)
            logger.info("Groww session authenticated (direct token).")
            return groww

        # Checksum flow: API Key + Secret
        timestamp = str(int(time.time()))
        checksum = self._generate_checksum(self._config.api_secret, timestamp)

        resp = requests.post(
            self.TOKEN_URL,
            headers={
                "Authorization": f"Bearer {self._config.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "key_type": "approval",
                "checksum": checksum,
                "timestamp": timestamp,
            },
            timeout=10,
        )

        if resp.status_code != 200:
            raise RuntimeError(f"Groww auth failed ({resp.status_code}): {resp.text}")

        data = resp.json()
        access_token = data.get("payload", {}).get("token") or data.get("token")
        if not access_token:
            raise RuntimeError(f"No token in response: {data}")

        groww = GrowwAPI(access_token)
        logger.info("Groww session authenticated (checksum flow).")
        return groww

    @staticmethod
    def _generate_checksum(secret: str, timestamp: str) -> str:
        input_str = secret + timestamp
        return hashlib.sha256(input_str.encode("utf-8")).hexdigest()
