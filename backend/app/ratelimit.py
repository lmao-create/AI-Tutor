"""Tiny in-memory sliding-window rate limiter.

Good enough for a local single-user deployment; swap the `hits` store for
Redis if this is ever deployed for many users.
"""
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Tuple

from .config import settings
from .errors import RateLimitedError

_hits: Dict[str, Deque[float]] = defaultdict(deque)


def check_limit(bucket: str, ident: str = "local") -> None:
    """Raise 429 if the (bucket, ident) pair exceeded its window quota."""
    limits = settings.rate_limits
    if bucket not in limits:
        return
    max_requests, window = limits[bucket]
    now = time.monotonic()
    key = f"{bucket}:{ident}"
    q = _hits[key]
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= max_requests:
        retry_after = int(window - (now - q[0])) + 1
        raise RateLimitedError(retry_after=retry_after)
    q.append(now)
