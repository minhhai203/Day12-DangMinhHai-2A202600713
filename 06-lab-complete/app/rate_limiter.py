"""Redis sliding-window rate limiter."""
from __future__ import annotations

import time
import uuid

from fastapi import HTTPException

from app.config import settings
from app.storage import storage


_SLIDING_WINDOW = storage.client.register_script(
    """
    redis.call('ZREMRANGEBYSCORE', KEYS[1], 0, tonumber(ARGV[1]) - tonumber(ARGV[2]))
    local count = redis.call('ZCARD', KEYS[1])
    if count >= tonumber(ARGV[3]) then
        return {0, count}
    end
    redis.call('ZADD', KEYS[1], ARGV[1], ARGV[4])
    redis.call('EXPIRE', KEYS[1], 60)
    return {1, count + 1}
    """
)


def check_rate_limit(user_id: str) -> dict[str, int]:
    now_ms = int(time.time() * 1000)
    window_ms = 60_000
    key = f"rate:{user_id}"
    allowed, count = _SLIDING_WINDOW(
        keys=[key],
        args=[
            now_ms,
            window_ms,
            settings.rate_limit_per_minute,
            f"{now_ms}:{uuid.uuid4().hex}",
        ],
    )

    if int(allowed) != 1:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: {settings.rate_limit_per_minute} requests/minute",
            headers={"Retry-After": "60"},
        )

    return {
        "limit": settings.rate_limit_per_minute,
        "remaining": settings.rate_limit_per_minute - int(count),
    }
