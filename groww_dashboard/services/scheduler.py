"""Background scheduler for periodic alert checks."""

import logging
import threading
import time

logger = logging.getLogger(__name__)


class AlertScheduler:
    """Runs alert checks on a background thread at fixed intervals."""

    def __init__(self, alerts_engine, interval_minutes: int = 30):
        self._engine = alerts_engine
        self._interval = interval_minutes * 60
        self._running = False
        self._thread = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info("Alert scheduler started (every %d min).", self._interval // 60)

    def stop(self):
        self._running = False

    def _loop(self):
        while self._running:
            try:
                self._engine.check_and_alert()
            except Exception as e:
                logger.error("Scheduler error: %s", e)
            time.sleep(self._interval)
