"""Session management: Groww API authentication (TOTP, checksum, or direct token)."""

import hashlib
import logging
import time

import pyotp
from growwapi import GrowwAPI

from groww_dashboard.config import GrowwConfig

logger = logging.getLogger(__name__)


class SessionManager:
    """Handles Groww authentication. Tries TOTP first, then checksum, then direct token."""

    def __init__(self, config: GrowwConfig):
        self._config = config
        self._groww: GrowwAPI | None = None

    def login(self) -> GrowwAPI:
        self._groww = self._authenticate()
        return self._groww

    def refresh(self) -> GrowwAPI:
        """Re-authenticate and return a fresh session."""
        logger.info("Refreshing Groww session...")
        self._groww = self._authenticate()
        return self._groww

    @property
    def client(self) -> GrowwAPI:
        return self._groww

    def _authenticate(self) -> GrowwAPI:
        # TOTP flow (fully automated, no daily approval)
        if self._config.totp_secret:
            totp = pyotp.TOTP(self._config.totp_secret).now()
            logger.info("TOTP generated at time: %s", int(time.time()))
            access_token = GrowwAPI.get_access_token(
                api_key=self._config.api_key, totp=totp
            )
            logger.info("Access token type: %s, value: %s...", type(access_token).__name__, str(access_token)[:30])
            groww = GrowwAPI(access_token)
            logger.info("Groww session authenticated (TOTP).")
            return groww

        # Direct token (if api_key is already a JWT)
        if self._config.api_key.startswith("eyJ"):
            groww = GrowwAPI(self._config.api_key)
            logger.info("Groww session authenticated (direct token).")
            return groww

        # Checksum flow (requires daily approval)
        timestamp = str(int(time.time()))
        checksum = hashlib.sha256(
            (self._config.api_secret + timestamp).encode()
        ).hexdigest()
        access_token = GrowwAPI.get_access_token(
            api_key=self._config.api_key, secret=self._config.api_secret
        )
        groww = GrowwAPI(access_token)
        logger.info("Groww session authenticated (checksum).")
        return groww
