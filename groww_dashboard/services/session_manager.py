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
        """Authenticate with Groww using access token directly."""
        groww = GrowwAPI(self._config.api_key)
        logger.info("Groww session authenticated successfully.")
        return groww
