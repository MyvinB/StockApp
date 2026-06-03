"""Session management: Groww API Key + Secret authentication."""

import logging

from growwapi import GrowwAPI

from groww_dashboard.config import GrowwConfig

logger = logging.getLogger(__name__)


class SessionManager:
    """Handles Groww authentication via API Key + Secret."""

    def __init__(self, config: GrowwConfig):
        self._config = config

    def login(self) -> GrowwAPI:
        """Get access token using API key and secret."""
        access_token = GrowwAPI.get_access_token(
            api_key=self._config.api_key, secret=self._config.api_secret
        )
        groww = GrowwAPI(access_token)
        logger.info("Groww session authenticated successfully.")
        return groww
