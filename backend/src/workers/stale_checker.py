"""Periodic stale job detection.

Runs as a background thread within the API process or as a standalone process.
Checks for jobs with expired heartbeats and re-queues or fails them.
"""

import logging
import time

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .queue import requeue_stale_jobs

logger = logging.getLogger(__name__)

DEFAULT_CHECK_INTERVAL = 30  # seconds
DEFAULT_HEARTBEAT_TIMEOUT = 120  # seconds


class StaleChecker:
    def __init__(
        self,
        db_url: str = "sqlite:///./palm4u.db",
        check_interval: int = DEFAULT_CHECK_INTERVAL,
        heartbeat_timeout: int = DEFAULT_HEARTBEAT_TIMEOUT,
    ):
        self.engine = create_engine(db_url)
        self.SessionFactory = sessionmaker(bind=self.engine)
        self.check_interval = check_interval
        self.heartbeat_timeout = heartbeat_timeout
        self._running = True

    def start(self) -> None:
        logger.info("Stale checker started (interval=%ds, timeout=%ds)",
                     self.check_interval, self.heartbeat_timeout)
        while self._running:
            try:
                session = self.SessionFactory()
                try:
                    count = requeue_stale_jobs(session, self.heartbeat_timeout)
                    if count:
                        logger.warning("Requeued %d stale jobs", count)
                finally:
                    session.close()
            except Exception:
                logger.exception("Error in stale checker")
            time.sleep(self.check_interval)

        self.engine.dispose()
        logger.info("Stale checker stopped")

    def stop(self) -> None:
        self._running = False
