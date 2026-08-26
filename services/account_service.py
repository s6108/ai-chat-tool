from datetime import datetime, timezone
from typing import Any


def format_subscription_date(value: Any) -> str:
    """
    把 Supabase 返回的 ISO 时间格式化为 YYYY-MM-DD。
    没有日期时返回短横线。
    """
    if not value:
        return "—"

    try:
        text = str(value).replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
        return parsed.strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return str(value)


def _parse_datetime(value: Any):
    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _is_future(value: Any) -> bool:
    parsed = _parse_datetime(value)
    return bool(
        parsed
        and parsed > datetime.now(timezone.utc)
    )


def _subscription_is_premium(subscription: dict[str, Any]) -> bool:
    plan = str(
        subscription.get("plan") or "free"
    ).strip().lower()

    status = str(
        subscription.get("status") or ""
    ).strip().lower()

    if plan != "premium":
        return False

    # 正常订阅状态。
    if status in {
        "active",
        "on_trial",
        "paused",
        "past_due",
    }:
        return True

    # 用户取消自动续费后，在当前付费周期结束前仍保持 Premium。
    if status == "cancelled":
        period_end = (
            subscription.get("ends_at")
            or subscription.get("current_period_end")
        )
        return _is_future(period_end)

    return False


def get_account_data(
    supabase_admin,
    user,
) -> dict[str, Any]:
    """
    获取当前用户的账户、自动订阅和 30-Day Pass 信息。

    Premium 判断：
    1. 有效 Lemon Squeezy 自动订阅；
    2. 或有效 30-Day Pass。

    两者任意一个有效，用户即为 Premium。
    """
    user_id = str(user.id)
    user_email = getattr(user, "email", None) or "用户"

    # -------------------------
    # Subscription
    # -------------------------
    try:
        result = (
            supabase_admin
            .table("user_subscriptions")
            .select(
                "email,"
                "plan,"
                "status,"
                "current_period_end,"
                "ends_at,"
                "cancelled_at,"
                "lemonsqueezy_customer_id,"
                "lemonsqueezy_subscription_id"
            )
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )

        subscription = (
            result.data[0]
            if result.data
            else {}
        )

    except Exception as exc:
        print(f"Account subscription load failed: {exc}")
        subscription = {}

    subscription_is_premium = _subscription_is_premium(
        subscription
    )

    subscription_period_end = (
        subscription.get("ends_at")
        or subscription.get("current_period_end")
    )

    # -------------------------
    # 30-Day Pass
    # -------------------------
    try:
        pass_result = (
            supabase_admin
            .table("user_passes")
            .select(
                "id,"
                "email,"
                "pass_type,"
                "status,"
                "starts_at,"
                "expires_at,"
                "lemonsqueezy_order_id"
            )
            .eq("user_id", user_id)
            .eq("status", "active")
            .order("expires_at", desc=True)
            .limit(1)
            .execute()
        )

        active_pass = (
            pass_result.data[0]
            if pass_result.data
            else {}
        )

    except Exception as exc:
        print(f"Account pass load failed: {exc}")
        active_pass = {}

    pass_expires_at = active_pass.get("expires_at")
    pass_is_premium = _is_future(pass_expires_at)

    # -------------------------
    # Effective account state
    # -------------------------
    is_premium = (
        subscription_is_premium
        or pass_is_premium
    )

    if subscription_is_premium:
        access_type = "subscription"
        plan = "premium"
        status = str(
            subscription.get("status") or "active"
        ).strip().lower()
        period_end = subscription_period_end

    elif pass_is_premium:
        access_type = "pass"
        plan = "premium"
        status = "active"
        period_end = pass_expires_at

    else:
        access_type = "free"
        plan = "free"
        status = "free"
        period_end = None

    return {
        "user_id": user_id,
        "email": (
            subscription.get("email")
            or active_pass.get("email")
            or user_email
        ),
        "plan": plan,
        "status": status,
        "access_type": access_type,
        "period_end_raw": period_end,
        "period_end_display": format_subscription_date(
            period_end
        ),
        "cancelled_at_display": format_subscription_date(
            subscription.get("cancelled_at")
        ),
        "customer_id": subscription.get(
            "lemonsqueezy_customer_id"
        ),
        "subscription_id": (
            subscription.get(
                "lemonsqueezy_subscription_id"
            )
            if subscription_is_premium
            else None
        ),
        "pass_id": active_pass.get("id"),
        "pass_type": active_pass.get("pass_type"),
        "pass_expires_at_raw": pass_expires_at,
        "pass_expires_at_display": format_subscription_date(
            pass_expires_at
        ),
        "is_subscription_premium": subscription_is_premium,
        "is_pass_premium": pass_is_premium,
        "is_premium": is_premium,
    }
