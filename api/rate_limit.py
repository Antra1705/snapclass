"""Minimal fixed-window rate limiter for code-guessing endpoints.

In-memory and per-process (same caveat as the face batch store); a
multi-worker deployment needs a shared backend (e.g. Redis).
"""

import threading
import time

from fastapi import HTTPException, Request


class FixedWindowRateLimiter:
    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._lock = threading.Lock()
        self._windows: dict[str, tuple[float, int]] = {}

    def check(self, key: str) -> None:
        """Count one request for key; raise 429 when over the limit."""
        now = time.time()
        with self._lock:
            window_start, count = self._windows.get(key, (now, 0))
            if now - window_start >= self.window_seconds:
                window_start, count = now, 0
            count += 1
            self._windows[key] = (window_start, count)

        if count > self.max_requests:
            retry_after = int(self.window_seconds - (now - window_start)) + 1
            raise HTTPException(
                status_code=429,
                detail="Too many attempts, please try again later",
                headers={"Retry-After": str(retry_after)},
            )


def client_ip(request: Request) -> str:
    """Best-effort client IP.

    Honors the first hop in X-Forwarded-For so the limiter works behind a
    reverse proxy. NOTE: X-Forwarded-For is client-spoofable unless a trusted
    proxy overwrites it — in production only trust it from your own ingress.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


# Subject-code guessing surface: enroll-by-code and code lookup.
# Per-authenticated-user budget (stops a single logged-in user hammering).
subject_code_rate_limiter = FixedWindowRateLimiter(max_requests=10, window_seconds=60)
# Per-IP budget across enroll + lookup. This is the one that survives
# account-cycling, since a new student account does not change the source IP.
subject_code_ip_rate_limiter = FixedWindowRateLimiter(max_requests=20, window_seconds=60)
# Per-IP cap on public student registration, so an attacker cannot mint fresh
# accounts to reset the per-user code-guessing budget.
register_ip_rate_limiter = FixedWindowRateLimiter(max_requests=5, window_seconds=60)
