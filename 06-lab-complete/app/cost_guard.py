"""Redis-backed monthly LLM budget protection."""
from __future__ import annotations

import calendar
from datetime import datetime, timezone
from typing import Union

from fastapi import HTTPException

from app.config import settings
from app.storage import storage


PRICE_PER_1K_INPUT_TOKENS = 0.00015
PRICE_PER_1K_OUTPUT_TOKENS = 0.0006

_CHECK_AND_RECORD = storage.client.register_script(
    """
    local current = tonumber(redis.call('GET', KEYS[1]) or '0')
    local estimate = tonumber(ARGV[1])
    local budget = tonumber(ARGV[2])
    if current + estimate > budget then
        return {0, tostring(current)}
    end
    local updated = redis.call('INCRBYFLOAT', KEYS[1], estimate)
    redis.call('EXPIRE', KEYS[1], tonumber(ARGV[3]))
    return {1, tostring(updated)}
    """
)


def _month_key(user_id: str) -> tuple[str, int]:
    now = datetime.now(timezone.utc)
    days = calendar.monthrange(now.year, now.month)[1]
    return f"cost:{user_id}:{now:%Y-%m}", (days + 1) * 24 * 60 * 60


def estimate_cost(input_tokens: int, output_tokens: int) -> float:
    return (
        input_tokens / 1000 * PRICE_PER_1K_INPUT_TOKENS
        + output_tokens / 1000 * PRICE_PER_1K_OUTPUT_TOKENS
    )


def check_and_record_cost(user_id: str, input_tokens: int, output_tokens: int) -> float:
    key, ttl = _month_key(user_id)
    cost = max(estimate_cost(input_tokens, output_tokens), 0.000001)
    allowed, total = _CHECK_AND_RECORD(
        keys=[key],
        args=[cost, settings.monthly_budget_usd, ttl],
    )
    total_cost = float(total)
    if int(allowed) != 1:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "Monthly budget exceeded",
                "used_usd": round(total_cost, 6),
                "budget_usd": settings.monthly_budget_usd,
            },
        )
    return total_cost


def get_usage(user_id: str) -> dict[str, Union[float, str]]:
    key, _ = _month_key(user_id)
    current = float(storage.client.get(key) or 0)
    return {
        "month": datetime.now(timezone.utc).strftime("%Y-%m"),
        "cost_usd": round(current, 6),
        "budget_usd": settings.monthly_budget_usd,
        "remaining_usd": round(max(0, settings.monthly_budget_usd - current), 6),
    }
