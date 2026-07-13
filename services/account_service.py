from datetime import datetime
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


def get_account_data(
    supabase_admin,
    user,
) -> dict[str, Any]:
    """
    获取当前用户的账户和订阅信息。

    没有订阅记录时自动返回 Free 套餐，
    不会因为查不到记录而导致页面报错。
    """
    user_id = str(user.id)
    user_email = getattr(user, "email", None) or "用户"

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

        if result.data:
            subscription = result.data[0]
        else:
            subscription = {}

    except Exception as exc:
        print(f"Account subscription load failed: {exc}")
        subscription = {}

    plan = str(
        subscription.get("plan") or "free"
    ).strip().lower()

    status = str(
        subscription.get("status") or (
            "active" if plan == "premium" else "free"
        )
    ).strip().lower()

    period_end = (
        subscription.get("ends_at")
        or subscription.get("current_period_end")
    )

    return {
        "user_id": user_id,
        "email": (
            subscription.get("email")
            or user_email
        ),
        "plan": plan,
        "status": status,
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
        "subscription_id": subscription.get(
            "lemonsqueezy_subscription_id"
        ),
        "is_premium": plan == "premium",
    }