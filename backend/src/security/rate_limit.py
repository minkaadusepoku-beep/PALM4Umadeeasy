"""Simple in-memory rate limiter for auth endpoints."""

import time
import threading
from collections import defaultdict


class RateLimiter:
    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def is_allowed(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            timestamps = self._requests[key]
            # Prune expired entries
            cutoff = now - self.window
            self._requests[key] = [t for t in timestamps if t > cutoff]
            timestamps = self._requests[key]

            if len(timestamps) >= self.max_requests:
                return False

            timestamps.append(now)
            return True

    def remaining(self, key: str) -> int:
        now = time.monotonic()
        with self._lock:
            cutoff = now - self.window
            timestamps = [t for t in self._requests[key] if t > cutoff]
            return max(0, self.max_requests - len(timestamps))


# Global rate limiters
import os

_rate_limit = int(os.getenv("PALM4U_AUTH_RATE_LIMIT", "10"))
auth_limiter = RateLimiter(max_requests=_rate_limit, window_seconds=60)
