from __future__ import annotations

import threading
import time


class TokenBucket:
    def __init__(self, rpm: float = 60.0, burst: float = 10.0) -> None:
        self._rate = rpm / 60.0
        self._burst = burst
        self._tokens = burst
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self) -> float:
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._tokens = min(self._burst, self._tokens + elapsed * self._rate)
            self._last_refill = now

            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return 0.0

            wait = (1.0 - self._tokens) / self._rate
            self._tokens = 0.0
            return wait
