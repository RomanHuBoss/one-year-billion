from __future__ import annotations
import time
from dataclasses import dataclass


@dataclass
class TokenBucketRateLimiter:
    """Простой локальный limiter, чтобы retry/reconnect не создавали order storm."""

    rate_per_second: float = 5.0
    burst: int = 10
    _tokens: float = 10.0
    _updated_at: float = time.monotonic()

    def allow(self) -> bool:
        now = time.monotonic()
        elapsed = max(now - self._updated_at, 0.0)
        self._tokens = min(float(self.burst), self._tokens + elapsed * self.rate_per_second)
        self._updated_at = now
        if self._tokens < 1.0:
            return False
        self._tokens -= 1.0
        return True
