from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Optional
from uuid import uuid4
from time import monotonic


# ============================================================
# Legacy daily request limits
# ============================================================

FREE_DAILY_CHAT_LIMIT = 8
FREE_DAILY_IMAGE_LIMIT = 2

# 暂时保留旧常量，避免 app.py 现有 import 失效。
# Pro 最终是否允许请求，不再依赖这两个数字，
# 后面统一交给 Credit / Fair Use 系统判断。
PREMIUM_DAILY_CHAT_LIMIT = 100
PREMIUM_DAILY_IMAGE_LIMIT = 25


# backward compatibility
FREE_CHAT_LIMIT = FREE_DAILY_CHAT_LIMIT
FREE_IMAGE_LIMIT = FREE_DAILY_IMAGE_LIMIT

PREMIUM_CHAT_LIMIT = PREMIUM_DAILY_CHAT_LIMIT
PREMIUM_IMAGE_LIMIT = PREMIUM_DAILY_IMAGE_LIMIT


# ============================================================
# Credit / Cost configuration
# ============================================================

CREDIT_PER_USD = Decimal("1000000")

# 第一版内部采用保守换算：
# 1 CNY 按 0.15 USD 计算。
#
# 这里不是对用户展示的实时汇率，
# 而是 Megor 内部成本保护汇率。
# 以后我们会把它移到数据库配置中。
CNY_TO_USD = Decimal("0.15")


@dataclass
class UsageCostResult:
    model_key: str
    provider_model_id: str
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int
    tool_cost_usd: Decimal
    estimated_cost_usd: Decimal
    credits: Decimal


# ============================================================
# Lightweight in-process caches
# ============================================================
#
# Goals:
# 1. Do not hit Supabase on every request for stable configuration.
# 2. Do not re-read daily request counters on every request.
# 3. For Credit/Fair-Use preflight, reuse the local snapshot while
#    remaining credit is safely above 10%.
# 4. Every successful record_usage_event updates the local credit
#    snapshot immediately, so the cache approaches the 10% threshold
#    without requiring a read before every model request.
#
# A short TTL is still kept as a multi-device / multi-worker safety net.
# A process restart simply causes one strict refresh.

CONFIG_CACHE_TTL_SECONDS = 300.0
DAILY_REQUEST_CACHE_TTL_SECONDS = 300.0
USAGE_STATUS_CACHE_TTL_SECONDS = 300.0
STRICT_CREDIT_RECHECK_PERCENT = 10.0

_MODEL_COST_CACHE: dict[str, tuple[float, dict]] = {}
_PLAN_LIMITS_CACHE: dict[str, tuple[float, dict]] = {}
_DAILY_REQUEST_CACHE: dict[str, tuple[float, dict]] = {}
_USAGE_STATUS_CACHE: dict[tuple[str, str], tuple[float, dict]] = {}


def _cache_get(
    cache: dict,
    key: Any,
    ttl_seconds: float,
):
    item = cache.get(key)

    if not item:
        return None

    cached_at, value = item

    if (
        monotonic() - cached_at
        > ttl_seconds
    ):
        cache.pop(key, None)
        return None

    if isinstance(value, dict):
        return dict(value)

    return value


def _cache_set(
    cache: dict,
    key: Any,
    value: Any,
) -> None:
    if isinstance(value, dict):
        value = dict(value)

    cache[key] = (
        monotonic(),
        value,
    )


def _minimum_remaining_percent(
    status: dict,
) -> float | None:
    values = []

    for key in (
        "daily_remaining_percent",
        "monthly_remaining_percent",
    ):
        value = status.get(key)

        if value is None:
            continue

        try:
            values.append(float(value))
        except (TypeError, ValueError):
            continue

    if not values:
        return None

    return min(values)



def get_minimum_remaining_percent(
    status: dict | None,
) -> float | None:
    """Public helper for app/session-level quota gating."""
    if not status:
        return None

    return _minimum_remaining_percent(status)

def _cache_usage_status(
    user_id: str,
    plan: str,
    status: dict,
) -> None:
    plan_key = _normalize_plan_key(plan)

    _cache_set(
        _USAGE_STATUS_CACHE,
        (str(user_id), plan_key),
        status,
    )


def _get_cached_usage_status(
    user_id: str,
    plan: str,
) -> dict | None:
    plan_key = _normalize_plan_key(plan)

    return _cache_get(
        _USAGE_STATUS_CACHE,
        (str(user_id), plan_key),
        USAGE_STATUS_CACHE_TTL_SECONDS,
    )


def _apply_recorded_credits_to_cache(
    user_id: str,
    credits: Decimal,
) -> None:
    """Update cached daily/monthly credit usage after a successful write."""

    credit_value = max(
        float(credits),
        0.0,
    )

    if credit_value <= 0:
        return

    user_id = str(user_id)

    for cache_key, cache_item in list(
        _USAGE_STATUS_CACHE.items()
    ):
        cached_user_id, _plan_key = cache_key

        if cached_user_id != user_id:
            continue

        cached_at, status = cache_item
        status = dict(status)

        daily_used = float(
            status.get(
                "daily_used_credits",
                0.0,
            )
            or 0.0
        ) + credit_value

        monthly_used = float(
            status.get(
                "monthly_used_credits",
                0.0,
            )
            or 0.0
        ) + credit_value

        status[
            "daily_used_credits"
        ] = daily_used

        status[
            "monthly_used_credits"
        ] = monthly_used

        daily_limit = status.get(
            "daily_credit_limit"
        )

        monthly_limit = status.get(
            "monthly_credit_limit"
        )

        if daily_limit is not None:
            daily_limit = float(
                daily_limit
            )

            if daily_limit > 0:
                status[
                    "daily_remaining_percent"
                ] = max(
                    0.0,
                    min(
                        100.0,
                        100.0
                        * (
                            1.0
                            - daily_used
                            / daily_limit
                        ),
                    ),
                )

            status[
                "daily_exhausted"
            ] = (
                daily_used
                >= daily_limit
            )

        if monthly_limit is not None:
            monthly_limit = float(
                monthly_limit
            )

            if monthly_limit > 0:
                status[
                    "monthly_remaining_percent"
                ] = max(
                    0.0,
                    min(
                        100.0,
                        100.0
                        * (
                            1.0
                            - monthly_used
                            / monthly_limit
                        ),
                    ),
                )

            status[
                "monthly_exhausted"
            ] = (
                monthly_used
                >= monthly_limit
            )

        status["allowed"] = not (
            status.get(
                "daily_exhausted",
                False,
            )
            or status.get(
                "monthly_exhausted",
                False,
            )
        )

        # Keep original timestamp: TTL still forces an occasional
        # server reconciliation for multi-device / multi-worker use.
        _USAGE_STATUS_CACHE[
            cache_key
        ] = (
            cached_at,
            status,
        )


# ============================================================
# Small helpers
# ============================================================

def _to_decimal(
    value: Any,
    default: str = "0",
) -> Decimal:
    if value is None:
        return Decimal(default)

    return Decimal(str(value))


def _money_to_usd(
    value: Decimal,
    currency: str,
) -> Decimal:
    currency = str(currency or "USD").upper()

    if currency == "USD":
        return value

    if currency == "CNY":
        return value * CNY_TO_USD

    raise ValueError(
        f"Unsupported model cost currency: {currency}"
    )


# ============================================================
# Existing daily request usage
# ============================================================

def get_today_usage(
    supabase_admin,
    user_id: str,
    *,
    force_refresh: bool = False,
) -> dict:
    today = date.today().isoformat()
    cache_key = str(user_id)

    if not force_refresh:
        cached = _cache_get(
            _DAILY_REQUEST_CACHE,
            cache_key,
            DAILY_REQUEST_CACHE_TTL_SECONDS,
        )

        if (
            cached
            and cached.get(
                "usage_date"
            ) == today
        ):
            return cached

    result = (
        supabase_admin
        .table("user_usage")
        .select("*")
        .eq("user_id", user_id)
        .eq("usage_date", today)
        .limit(1)
        .execute()
    )

    if result.data:
        usage = result.data[0]

        _cache_set(
            _DAILY_REQUEST_CACHE,
            cache_key,
            usage,
        )

        return usage

    new_usage = {
        "user_id": user_id,
        "usage_date": today,
        "chat_count": 0,
        "image_count": 0,
    }

    (
        supabase_admin
        .table("user_usage")
        .insert(new_usage)
        .execute()
    )

    _cache_set(
        _DAILY_REQUEST_CACHE,
        cache_key,
        new_usage,
    )

    return new_usage

def increase_chat_usage(
    supabase_admin,
    user_id: str,
) -> int:
    usage = get_today_usage(
        supabase_admin,
        user_id,
    )

    new_count = (
        int(usage.get("chat_count", 0))
        + 1
    )

    (
        supabase_admin
        .table("user_usage")
        .update(
            {
                "chat_count": new_count
            }
        )
        .eq("user_id", user_id)
        .eq(
            "usage_date",
            usage["usage_date"],
        )
        .execute()
    )

    cached_usage = dict(usage)
    cached_usage[
        "chat_count"
    ] = new_count

    _cache_set(
        _DAILY_REQUEST_CACHE,
        str(user_id),
        cached_usage,
    )

    return new_count


def increase_image_usage(
    supabase_admin,
    user_id: str,
) -> int:
    usage = get_today_usage(
        supabase_admin,
        user_id,
    )

    new_count = (
        int(usage.get("image_count", 0))
        + 1
    )

    (
        supabase_admin
        .table("user_usage")
        .update(
            {
                "image_count": new_count
            }
        )
        .eq("user_id", user_id)
        .eq(
            "usage_date",
            usage["usage_date"],
        )
        .execute()
    )

    cached_usage = dict(usage)
    cached_usage[
        "image_count"
    ] = new_count

    _cache_set(
        _DAILY_REQUEST_CACHE,
        str(user_id),
        cached_usage,
    )

    return new_count


def can_use_chat(
    supabase_admin,
    user_id: str,
    plan: str = "free",
) -> bool:
    normalized_plan = str(
        plan or "free"
    ).lower()

    # Pro / premium does not use the legacy daily request hard cap.
    # Crucially, return before touching Supabase.
    if normalized_plan in {
        "pro",
        "premium",
        "paid",
    }:
        return True

    usage = get_today_usage(
        supabase_admin,
        user_id,
    )

    return (
        int(
            usage.get(
                "chat_count",
                0,
            )
        )
        < FREE_DAILY_CHAT_LIMIT
    )

def can_use_image(
    supabase_admin,
    user_id: str,
    plan: str = "free",
) -> bool:
    normalized_plan = str(
        plan or "free"
    ).lower()

    if normalized_plan in {
        "pro",
        "premium",
        "paid",
    }:
        return True

    usage = get_today_usage(
        supabase_admin,
        user_id,
    )

    return (
        int(
            usage.get(
                "image_count",
                0,
            )
        )
        < FREE_DAILY_IMAGE_LIMIT
    )


# ============================================================
# Model cost configuration
# ============================================================

def get_model_cost_config(
    supabase_admin,
    model_key: str,
) -> Optional[dict]:
    cache_key = str(model_key)

    cached = _cache_get(
        _MODEL_COST_CACHE,
        cache_key,
        CONFIG_CACHE_TTL_SECONDS,
    )

    if cached is not None:
        return cached

    result = (
        supabase_admin
        .table("model_costs")
        .select("*")
        .eq(
            "model_key",
            model_key,
        )
        .eq(
            "is_active",
            True,
        )
        .limit(1)
        .execute()
    )

    if not result.data:
        return None

    config = result.data[0]

    _cache_set(
        _MODEL_COST_CACHE,
        cache_key,
        config,
    )

    return config


# ============================================================
# Credit calculation
# ============================================================

def calculate_usage_cost(
    supabase_admin,
    model_key: str,
    input_tokens: int,
    output_tokens: int,
    *,
    cached_input_tokens: int = 0,
    tool_cost_usd: float | Decimal = 0,
    provider_actual_cost_usd: (
        float | Decimal | None
    ) = None,
) -> UsageCostResult:

    config = get_model_cost_config(
        supabase_admin,
        model_key,
    )

    if not config:
        raise ValueError(
            "No active model cost configuration "
            f"found for: {model_key}"
        )

    input_tokens = max(
        int(input_tokens or 0),
        0,
    )

    output_tokens = max(
        int(output_tokens or 0),
        0,
    )

    cached_input_tokens = max(
        int(cached_input_tokens or 0),
        0,
    )

    cached_input_tokens = min(
        cached_input_tokens,
        input_tokens,
    )

    uncached_input_tokens = (
        input_tokens
        - cached_input_tokens
    )

    safety_multiplier = _to_decimal(
        config.get(
            "safety_multiplier"
        ),
        "1.15",
    )

    tool_cost_usd_decimal = _to_decimal(
        tool_cost_usd
    )

    # --------------------------------------------------------
    # 如果 provider 已经直接返回真实美元成本，
    # 优先使用真实成本。
    #
    # 例如后续 Grok 搜索可以使用
    # xAI 返回的实际请求成本。
    # --------------------------------------------------------

    if provider_actual_cost_usd is not None:

        raw_cost_usd = _to_decimal(
            provider_actual_cost_usd
        )

        # 如果真实 provider cost 已经包含 tool cost，
        # 调用时 tool_cost_usd 应传 0。
        raw_cost_usd += (
            tool_cost_usd_decimal
        )

    else:

        currency = str(
            config.get("currency")
            or "USD"
        ).upper()

        input_price = _to_decimal(
            config.get(
                "input_cost_per_million"
            )
        )

        output_price = _to_decimal(
            config.get(
                "output_cost_per_million"
            )
        )

        cached_input_price_raw = (
            config.get(
                "cached_input_cost_per_million"
            )
        )

        if (
            cached_input_price_raw
            is None
        ):
            cached_input_price = (
                input_price
            )
        else:
            cached_input_price = (
                _to_decimal(
                    cached_input_price_raw
                )
            )

        input_cost = (
            Decimal(
                uncached_input_tokens
            )
            * input_price
            / Decimal("1000000")
        )

        cached_input_cost = (
            Decimal(
                cached_input_tokens
            )
            * cached_input_price
            / Decimal("1000000")
        )

        output_cost = (
            Decimal(
                output_tokens
            )
            * output_price
            / Decimal("1000000")
        )

        token_cost_native = (
            input_cost
            + cached_input_cost
            + output_cost
        )

        token_cost_usd = (
            _money_to_usd(
                token_cost_native,
                currency,
            )
        )

        raw_cost_usd = (
            token_cost_usd
            + tool_cost_usd_decimal
        )

    estimated_cost_usd = (
        raw_cost_usd
        * safety_multiplier
    )

    credits = (
        estimated_cost_usd
        * CREDIT_PER_USD
    )

    return UsageCostResult(
        model_key=model_key,
        provider_model_id=str(
            config.get(
                "provider_model_id"
            )
            or ""
        ),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_input_tokens=(
            cached_input_tokens
        ),
        tool_cost_usd=(
            tool_cost_usd_decimal
        ),
        estimated_cost_usd=(
            estimated_cost_usd
        ),
        credits=credits,
    )


# ============================================================
# Record one model request
# ============================================================

def record_usage_event(
    supabase_admin,
    *,
    user_id: str,
    model_key: str,
    input_tokens: int,
    output_tokens: int,
    request_type: str = "text",
    cached_input_tokens: int = 0,
    tool_cost_usd: float | Decimal = 0,
    provider_actual_cost_usd: (
        float | Decimal | None
    ) = None,
    request_id: Optional[str] = None,
    success: bool = True,
    metadata: Optional[dict] = None,
) -> UsageCostResult:

    cost_result = calculate_usage_cost(
        supabase_admin,
        model_key,
        input_tokens,
        output_tokens,
        cached_input_tokens=(
            cached_input_tokens
        ),
        tool_cost_usd=(
            tool_cost_usd
        ),
        provider_actual_cost_usd=(
            provider_actual_cost_usd
        ),
    )

    event_request_id = (
        request_id
        or str(uuid4())
    )

    event_metadata = dict(
        metadata or {}
    )

    event_metadata[
        "cached_input_tokens"
    ] = cached_input_tokens

    payload = {
        "user_id": user_id,
        "request_id": (
            event_request_id
        ),
        "model_key": (
            cost_result.model_key
        ),
        "provider_model_id": (
            cost_result.provider_model_id
        ),
        "request_type": request_type,
        "input_tokens": (
            cost_result.input_tokens
        ),
        "output_tokens": (
            cost_result.output_tokens
        ),
        "tool_cost_usd": float(
            cost_result.tool_cost_usd
        ),
        "estimated_cost_usd": float(
            cost_result.estimated_cost_usd
        ),
        "credits": float(
            cost_result.credits
        ),
        "success": success,
        "metadata": event_metadata,
    }

    last_insert_error = None

    for attempt in range(1, 4):
        try:
            (
                supabase_admin
                .table("usage_events")
                .insert(payload)
                .execute()
            )

            last_insert_error = None
            break

        except Exception as insert_error:
            last_insert_error = insert_error

            if attempt < 3:
                import time

                wait_seconds = 0.5 * attempt

                print(
                    "⚠️ Usage insert failed, retrying:",
                    f"attempt={attempt}/3,",
                    f"wait={wait_seconds:.1f}s,",
                    f"error={repr(insert_error)}",
                )

                time.sleep(wait_seconds)

    if last_insert_error is not None:
        raise last_insert_error

    _apply_recorded_credits_to_cache(
        user_id,
        cost_result.credits,
    )

    return cost_result
# ============================================================
# Plan / Credit limits
# ============================================================

def _normalize_plan_key(
    plan: str | None,
) -> str:
    normalized = str(
        plan or "free"
    ).strip().lower()

    if normalized in {
        "pro",
        "premium",
        "paid",
    }:
        return "pro"

    return "free"


def get_plan_limits(
    supabase_admin,
    plan: str = "free",
) -> dict:
    plan_key = _normalize_plan_key(plan)

    cached = _cache_get(
        _PLAN_LIMITS_CACHE,
        plan_key,
        CONFIG_CACHE_TTL_SECONDS,
    )

    if cached is not None:
        return cached

    result = (
        supabase_admin
        .table("usage_limits")
        .select("*")
        .eq("plan_key", plan_key)
        .eq("is_active", True)
        .limit(1)
        .execute()
    )

    if not result.data:
        raise ValueError(
            f"No active usage limits found "
            f"for plan: {plan_key}"
        )

    limits = result.data[0]

    _cache_set(
        _PLAN_LIMITS_CACHE,
        plan_key,
        limits,
    )

    return limits


# ============================================================
# Credit period helpers
# ============================================================

def _get_today_bounds() -> tuple[str, str]:
    """
    第一版按 UTC 日历日统计 Credit。

    后面如果 Megor 增加用户时区，
    再统一切换成用户本地日历日。
    """
    from datetime import (
        datetime,
        time,
        timedelta,
        timezone,
    )

    today = datetime.now(
        timezone.utc
    ).date()

    start = datetime.combine(
        today,
        time.min,
        tzinfo=timezone.utc,
    )

    end = start + timedelta(days=1)

    return (
        start.isoformat(),
        end.isoformat(),
    )


def _get_month_bounds() -> tuple[str, str]:
    from datetime import (
        datetime,
        timezone,
    )

    now = datetime.now(
        timezone.utc
    )

    start = datetime(
        year=now.year,
        month=now.month,
        day=1,
        tzinfo=timezone.utc,
    )

    if now.month == 12:
        end = datetime(
            year=now.year + 1,
            month=1,
            day=1,
            tzinfo=timezone.utc,
        )

    else:
        end = datetime(
            year=now.year,
            month=now.month + 1,
            day=1,
            tzinfo=timezone.utc,
        )

    return (
        start.isoformat(),
        end.isoformat(),
    )


# ============================================================
# Credit usage
# ============================================================

def _get_credit_usage_between(
    supabase_admin,
    user_id: str,
    start_iso: str,
    end_iso: str,
) -> Decimal:

    result = (
        supabase_admin
        .table("usage_events")
        .select("credits")
        .eq("user_id", user_id)
        .gte("created_at", start_iso)
        .lt("created_at", end_iso)
        .execute()
    )

    total = Decimal("0")

    for row in result.data or []:
        total += _to_decimal(
            row.get("credits")
        )

    return total


def get_daily_credit_usage(
    supabase_admin,
    user_id: str,
) -> Decimal:
    start_iso, end_iso = (
        _get_today_bounds()
    )

    return _get_credit_usage_between(
        supabase_admin,
        user_id,
        start_iso,
        end_iso,
    )


def get_monthly_credit_usage(
    supabase_admin,
    user_id: str,
) -> Decimal:
    start_iso, end_iso = (
        _get_month_bounds()
    )

    return _get_credit_usage_between(
        supabase_admin,
        user_id,
        start_iso,
        end_iso,
    )


# ============================================================
# Remaining percentage
# ============================================================

def _remaining_percent(
    used: Decimal,
    limit: Decimal | None,
) -> float | None:

    if limit is None:
        return None

    if limit <= 0:
        return 0.0

    remaining = (
        Decimal("100")
        * (
            Decimal("1")
            - (used / limit)
        )
    )

    if remaining < 0:
        remaining = Decimal("0")

    if remaining > 100:
        remaining = Decimal("100")

    return float(
        remaining.quantize(
            Decimal("0.1")
        )
    )


# ============================================================
# Unified usage status
# ============================================================

def get_usage_status(
    supabase_admin,
    *,
    user_id: str,
    plan: str = "free",
) -> dict:

    plan_key = _normalize_plan_key(
        plan
    )

    limits = get_plan_limits(
        supabase_admin,
        plan_key,
    )

    daily_used = (
        get_daily_credit_usage(
            supabase_admin,
            user_id,
        )
    )

    monthly_used = (
        get_monthly_credit_usage(
            supabase_admin,
            user_id,
        )
    )

    daily_limit_raw = limits.get(
        "daily_credit_limit"
    )

    monthly_limit_raw = limits.get(
        "monthly_credit_limit"
    )

    daily_limit = (
        _to_decimal(daily_limit_raw)
        if daily_limit_raw is not None
        else None
    )

    monthly_limit = (
        _to_decimal(monthly_limit_raw)
        if monthly_limit_raw is not None
        else None
    )

    daily_remaining_percent = (
        _remaining_percent(
            daily_used,
            daily_limit,
        )
    )

    monthly_remaining_percent = (
        _remaining_percent(
            monthly_used,
            monthly_limit,
        )
    )

    # --------------------------------------------------------
    # Hard limit
    # --------------------------------------------------------

    daily_exhausted = (
        daily_limit is not None
        and daily_used >= daily_limit
    )

    monthly_exhausted = (
        monthly_limit is not None
        and monthly_used >= monthly_limit
    )

    allowed = not (
        daily_exhausted
        or monthly_exhausted
    )

    # --------------------------------------------------------
    # Pro Fair Use
    # --------------------------------------------------------

    soft_limited = False
    heavy_limited = False
    cooldown_seconds = 0

    normal_max_output_tokens = (
        limits.get(
            "normal_max_output_tokens"
        )
    )

    heavy_max_output_tokens = (
        limits.get(
            "heavy_max_output_tokens"
        )
    )

    max_output_tokens = (
        normal_max_output_tokens
    )

    if plan_key == "pro":
        remaining = (
            monthly_remaining_percent
        )

        soft_threshold = float(
            limits.get(
                "soft_limit_percent"
            )
            or 0
        )

        heavy_threshold = float(
            limits.get(
                "heavy_limit_percent"
            )
            or 0
        )

        if (
            remaining is not None
            and remaining <= heavy_threshold
        ):
            heavy_limited = True
            soft_limited = True

            cooldown_seconds = int(
                limits.get(
                    "heavy_cooldown_seconds"
                )
                or 0
            )

            if (
                heavy_max_output_tokens
                is not None
            ):
                max_output_tokens = (
                    heavy_max_output_tokens
                )

        elif (
            remaining is not None
            and remaining <= soft_threshold
        ):
            soft_limited = True

            cooldown_seconds = int(
                limits.get(
                    "soft_cooldown_seconds"
                )
                or 0
            )

    status = {
        "plan_key": plan_key,

        "allowed": allowed,

        "daily_used_credits": float(
            daily_used
        ),

        "daily_credit_limit": (
            float(daily_limit)
            if daily_limit is not None
            else None
        ),

        "daily_remaining_percent": (
            daily_remaining_percent
        ),

        "monthly_used_credits": float(
            monthly_used
        ),

        "monthly_credit_limit": (
            float(monthly_limit)
            if monthly_limit is not None
            else None
        ),

        "monthly_remaining_percent": (
            monthly_remaining_percent
        ),

        "daily_exhausted": (
            daily_exhausted
        ),

        "monthly_exhausted": (
            monthly_exhausted
        ),

        "soft_limited": (
            soft_limited
        ),

        "heavy_limited": (
            heavy_limited
        ),

        "cooldown_seconds": (
            cooldown_seconds
        ),

        "max_output_tokens": (
            max_output_tokens
        ),

        
    }

    _cache_usage_status(
        user_id,
        plan_key,
        status,
    )

    return status

# ============================================================
# Preflight request protection
# ============================================================

# 这里不是模型真实成本，而是：
# “允许发起一次请求前，至少还要剩多少 Credit”
#
# 目的是防止：
# 剩余额度很少，但仍允许发起 Claude / Grok Search 等高成本请求。

FREE_BASIC_MODELS = {
    "DeepSeek",
    "Qwen",
    "Doubao-Pro",
    "GLM",
    "Kimi",
}

MODEL_MIN_REMAINING_CREDITS = {
    "DeepSeek": Decimal("3000"),
    "Qwen": Decimal("3000"),
    "Doubao-Pro": Decimal("5000"),
    "Kimi": Decimal("8000"),
    "GLM": Decimal("10000"),
    "ChatGPT": Decimal("10000"),
    "Gemini": Decimal("15000"),
    "Claude": Decimal("30000"),

    # Grok 普通聊天
    "Grok": Decimal("20000"),
}

# Grok 原生搜索需要单独保护。
NATIVE_SEARCH_MIN_REMAINING_CREDITS = {
    "Grok": Decimal("250000"),
}


def _remaining_credits(
    used: Decimal,
    limit: Decimal | None,
) -> Decimal | None:
    if limit is None:
        return None

    remaining = limit - used

    if remaining < 0:
        return Decimal("0")

    return remaining


def can_start_request(
    supabase_admin,
    *,
    user_id: str,
    plan: str,
    model_key: str,
    request_type: str = "text",
) -> dict:
    """
    调用模型 API 前执行的成本安全检查。

    返回：
    {
        "allowed": bool,
        "reason": str | None,
        "usage_status": {...},
        "required_remaining_credits": float,
        "available_remaining_credits": float | None,
    }
    """

    cached_status = (
        _get_cached_usage_status(
            user_id,
            plan,
        )
    )

    cached_remaining = (
        _minimum_remaining_percent(
            cached_status
        )
        if cached_status
        else None
    )

    # --------------------------------------------------------
    # Fast path:
    # Reuse the local snapshot while safely above 10%.
    #
    # The snapshot is updated after every record_usage_event,
    # and a short TTL still reconciles multi-device activity.
    # --------------------------------------------------------

    if (
        cached_status is not None
        and cached_status.get(
            "allowed",
            True,
        )
        and (
            cached_remaining is None
            or cached_remaining
            > STRICT_CREDIT_RECHECK_PERCENT
        )
    ):
        status = cached_status

        print(
            "⚡ Usage preflight cache hit:",
            {
                "remaining_percent": (
                    cached_remaining
                ),
                "strict_below": (
                    STRICT_CREDIT_RECHECK_PERCENT
                ),
            },
        )

    else:
        status = get_usage_status(
            supabase_admin,
            user_id=user_id,
            plan=plan,
        )

        print(
            "🔄 Usage preflight strict refresh:",
            {
                "remaining_percent": (
                    _minimum_remaining_percent(
                        status
                    )
                ),
            },
        )

    plan_key = status["plan_key"]



      

    # --------------------------------------------------------
    # 已经达到硬额度
    # --------------------------------------------------------

    if not status["allowed"]:
        return {
            "allowed": False,
            "reason": (
                "daily_credit_exhausted"
                if status["daily_exhausted"]
                else "monthly_credit_exhausted"
            ),
            "usage_status": status,
            "required_remaining_credits": 0.0,
            "available_remaining_credits": 0.0,
        }

    daily_used = _to_decimal(
        status.get("daily_used_credits")
    )

    monthly_used = _to_decimal(
        status.get("monthly_used_credits")
    )

    daily_limit_raw = status.get(
        "daily_credit_limit"
    )

    monthly_limit_raw = status.get(
        "monthly_credit_limit"
    )

    daily_limit = (
        _to_decimal(daily_limit_raw)
        if daily_limit_raw is not None
        else None
    )

    monthly_limit = (
        _to_decimal(monthly_limit_raw)
        if monthly_limit_raw is not None
        else None
    )

    daily_remaining = _remaining_credits(
        daily_used,
        daily_limit,
    )

    monthly_remaining = _remaining_credits(
        monthly_used,
        monthly_limit,
    )

    # --------------------------------------------------------
    # 当前请求至少需要多少剩余额度
    # --------------------------------------------------------

    normalized_request_type = str(
        request_type or "text"
    ).strip().lower()

    if normalized_request_type == "native_search":
        required = (
            NATIVE_SEARCH_MIN_REMAINING_CREDITS.get(
                model_key,
                Decimal("50000"),
            )
        )

    elif (
        plan_key == "free"
        and model_key in FREE_BASIC_MODELS
    ):
        # Free 用户的中国模型不做提前余额门槛。
        # 仍然受 Daily / Monthly hard limit
        # 和每日次数限制。
        required = Decimal("0")

    else:
        required = MODEL_MIN_REMAINING_CREDITS.get(
            model_key,
            Decimal("10000"),
        )

    

    # --------------------------------------------------------
    # Free：Daily 和 Monthly 两道门都检查
    # --------------------------------------------------------

    if plan_key == "free":

        if (
            daily_remaining is not None
            and daily_remaining < required
        ):
            return {
                "allowed": False,
                "reason": (
                    "insufficient_daily_credit_for_model"
                ),
                "usage_status": status,
                "required_remaining_credits": float(
                    required
                ),
                "available_remaining_credits": float(
                    daily_remaining
                ),
            }

        if (
            monthly_remaining is not None
            and monthly_remaining < required
        ):
            return {
                "allowed": False,
                "reason": (
                    "insufficient_monthly_credit_for_model"
                ),
                "usage_status": status,
                "required_remaining_credits": float(
                    required
                ),
                "available_remaining_credits": float(
                    monthly_remaining
                ),
            }

    # --------------------------------------------------------
    # Pro：主要检查 Monthly
    # --------------------------------------------------------

    if plan_key == "pro":

        if (
            monthly_remaining is not None
            and monthly_remaining < required
        ):
            return {
                "allowed": False,
                "reason": (
                    "insufficient_monthly_credit_for_model"
                ),
                "usage_status": status,
                "required_remaining_credits": float(
                    required
                ),
                "available_remaining_credits": float(
                    monthly_remaining
                ),
            }

    return {
        "allowed": True,
        "reason": None,
        "usage_status": status,
        "required_remaining_credits": float(
            required
        ),
        "available_remaining_credits": (
            float(
                min(
                    value
                    for value in (
                        daily_remaining,
                        monthly_remaining,
                    )
                    if value is not None
                )
            )
            if (
                daily_remaining is not None
                or monthly_remaining is not None
            )
            else None
        ),
    }