from __future__ import annotations

import asyncio
import random
import time
from functools import wraps
from typing import Any, Awaitable, Callable

from backend.config import settings


class ToolError(Exception):
    """Base tool exception."""


class ToolServerError(ToolError):
    """Transient server-side failure."""


class CorruptResponseError(ToolError):
    """Response shape does not match the tool contract."""


class MaxRetriesExceededError(ToolError):
    """Retry budget exhausted."""


class IrreversibleActionGuardError(ToolError):
    """Irreversible action attempted without the required guard."""


RNG = random.Random(settings.chaos_seed)

REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "get_customer": ("found", "email"),
    "get_order": ("found", "order_id"),
    "get_product": ("product_id", "return_window_days"),
    "search_knowledge_base": ("query", "results", "result_count"),
    "check_refund_eligibility": ("order_id", "eligible", "reason", "policy_flags"),
    "issue_refund": ("order_id", "amount_refunded", "status"),
    "send_reply": ("ticket_id", "delivered", "message_preview"),
    "escalate": ("ticket_id", "escalation_id", "routed_to"),
}


async def inject_chaos() -> None:
    if not settings.chaos_enabled:
        return

    draw = RNG.random()
    timeout_ceiling = settings.chaos_timeout_rate
    malformed_ceiling = timeout_ceiling + settings.chaos_malformed_rate
    server_error_ceiling = malformed_ceiling + settings.chaos_server_error_rate

    if draw < timeout_ceiling:
        await asyncio.sleep(5.2)
        raise TimeoutError("tool timed out")
    if draw < malformed_ceiling:
        raise CorruptResponseError("chaos injected a malformed payload")
    if draw < server_error_ceiling:
        raise ToolServerError("tool returned a synthetic 500")


def validate_schema(result: dict[str, Any], tool_name: str) -> None:
    if not isinstance(result, dict):
        raise CorruptResponseError(f"{tool_name} returned a non-dict result")
    for field in REQUIRED_FIELDS.get(tool_name, ()):
        if field not in result:
            raise CorruptResponseError(f"{tool_name} missing required field: {field}")
    if result.get("corrupt") is True:
        raise CorruptResponseError(f"{tool_name} returned a corrupt payload")


def timed_call_result(start: float, result: dict[str, Any]) -> tuple[dict[str, Any], int]:
    latency_ms = int((time.perf_counter() - start) * 1000)
    return result, latency_ms


def chaotic_tool(func: Callable[..., Awaitable[dict[str, Any]]]) -> Callable[..., Awaitable[dict[str, Any]]]:
    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(settings.max_retries):
            try:
                await inject_chaos()
                result = await asyncio.wait_for(func(*args, **kwargs), timeout=5.0)
                validate_schema(result, func.__name__)
                return result
            except (TimeoutError, ToolServerError, CorruptResponseError) as exc:
                last_error = exc
                if attempt == settings.max_retries - 1:
                    break
                delay = 1.0 * (2 ** attempt)
                await asyncio.sleep(delay)
        raise MaxRetriesExceededError(f"{func.__name__} failed after {settings.max_retries} attempts: {last_error}")

    return wrapper
