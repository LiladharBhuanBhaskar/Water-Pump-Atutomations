"""
HydraControl — In-Memory Sliding Window Rate Limiter (Phase 23.2).
Provides deterministic rate limiting with Retry-After headers, per-endpoint / per-IP scoping,
and test isolation without third-party external broker dependencies.
"""

import time
from typing import Dict, List, Tuple
from fastapi import Request, HTTPException, status


class RateLimiter:
    def __init__(self):
        # Key -> list of timestamps (epoch seconds)
        self._records: Dict[str, List[float]] = {}

    def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> Tuple[bool, int, int]:
        """
        Checks if the request under `key` is permitted within the sliding window.
        Returns:
            (allowed: bool, remaining_requests: int, retry_after_seconds: int)
        """
        now = time.time()
        cutoff = now - window_seconds

        # Clean expired timestamps for this key
        timestamps = self._records.get(key, [])
        valid_timestamps = [t for t in timestamps if t > cutoff]

        if len(valid_timestamps) >= max_requests:
            # Earliest timestamp within window + window_seconds = retry time
            earliest = valid_timestamps[0]
            retry_after = max(1, int(earliest + window_seconds - now))
            self._records[key] = valid_timestamps
            return False, 0, retry_after

        # Append current request
        valid_timestamps.append(now)
        self._records[key] = valid_timestamps
        remaining = max_requests - len(valid_timestamps)
        return True, remaining, 0

    def reset(self):
        """Resets rate limiting state for isolated test execution."""
        self._records.clear()


rate_limiter = RateLimiter()


def rate_limit(max_requests: int, window_seconds: int, key_prefix: str = "global"):
    """
    FastAPI dependency factory for endpoint-level rate limiting.
    Bypassed in development mode for smooth testing.
    """
    async def dependency(request: Request):
        try:
            from app.core.config import settings
            if settings.ENVIRONMENT == "development" or settings.DEBUG:
                return
        except Exception:
            pass

        # Derive identity key from client host / X-Forwarded-For
        client_ip = request.client.host if request.client else "127.0.0.1"
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()

        key = f"{key_prefix}:{client_ip}"
        allowed, remaining, retry_after = rate_limiter.is_allowed(key, max_requests, window_seconds)

        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too Many Requests: Rate limit of {max_requests} per {window_seconds}s exceeded.",
                headers={"Retry-After": str(retry_after)},
            )

    return dependency
