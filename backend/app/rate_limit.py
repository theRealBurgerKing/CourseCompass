"""Per-user rate limiting for the chat endpoint.

In-memory sliding window: counters live in this process only, so they reset on restart and
are not shared between instances. Fine for a single-instance deployment; swap in Redis if scaled out.
"""
import os
import threading
import time
from collections import deque
from fastapi import Depends, HTTPException
from app.dependencies import require_auth


class SlidingWindowLimiter:
    def __init__(self, limits: list[tuple[int, float]], clock=time.monotonic):
        """limits: [(max_requests, window_seconds), ...] — a request must satisfy every window."""
        self._limits = limits
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> int | None:
        """Record a request for key. Returns None if allowed, else seconds until it may retry."""
        now = self._clock()
        longest = max(w for _, w in self._limits)
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and now - hits[0] >= longest:
                hits.popleft()
            for max_requests, window in self._limits:
                in_window = [t for t in hits if now - t < window]
                if len(in_window) >= max_requests:
                    return max(1, int(in_window[0] + window - now) + 1)
            hits.append(now)
            # drop idle keys so the dict doesn't grow forever
            if len(self._hits) > 10_000:
                for k in [k for k, v in self._hits.items() if not v or now - v[-1] >= longest]:
                    del self._hits[k]
            return None

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, ""))
    except ValueError:
        return default


chat_limiter = SlidingWindowLimiter([
    (_env_int("RATE_LIMIT_PER_MINUTE", 10), 60),
    (_env_int("RATE_LIMIT_PER_DAY", 200), 86400),
])


def rate_limit_chat(user: dict = Depends(require_auth)) -> dict:
    """Authenticate, then enforce the per-user chat quota (HTTP 429 + Retry-After when exceeded)."""
    retry_after = chat_limiter.check(user.get("sub", "anonymous"))
    if retry_after is not None:
        raise HTTPException(
            status_code=429,
            detail=f"请求过于频繁，请 {retry_after} 秒后再试",
            headers={"Retry-After": str(retry_after)},
        )
    return user
