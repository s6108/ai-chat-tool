import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from typing import Any, Optional

from supabase import Client, create_client


class WebhookConfigurationError(Exception):
    """Webhook 或 Supabase 环境变量配置错误。"""


class InvalidWebhookSignature(Exception):
    """Webhook 签名验证失败。"""


class WebhookProcessingError(Exception):
    """Webhook 数据库处理失败。"""


# =========================================================
# Environment / Supabase
# =========================================================

def get_supabase_admin() -> Client:
    """
    创建使用 Service Role Key 的 Supabase 客户端。

    Webhook 是服务端程序，必须使用 SUPABASE_SERVICE_KEY，
    不能使用前端 anon key。
    """
    supabase_url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_KEY")

    if not supabase_url:
        raise WebhookConfigurationError("SUPABASE_URL 未配置")

    if not service_key:
        raise WebhookConfigurationError(
            "SUPABASE_SERVICE_KEY 未配置"
        )

    return create_client(supabase_url, service_key)


# =========================================================
# Signature verification
# =========================================================

def verify_webhook_signature(
    raw_body: bytes,
    received_signature: str,
) -> None:
    """
    验证 LemonSqueezy Webhook 签名。

    必须使用原始请求 body 计算 HMAC-SHA256。
    """
    webhook_secret = os.getenv(
        "LEMONSQUEEZY_WEBHOOK_SECRET"
    )

    if not webhook_secret:
        raise WebhookConfigurationError(
            "LEMONSQUEEZY_WEBHOOK_SECRET 未配置"
        )

    if not received_signature:
        raise InvalidWebhookSignature(
            "请求中缺少 X-Signature"
        )

    expected_signature = hmac.new(
        webhook_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(
        expected_signature,
        received_signature,
    ):
        raise InvalidWebhookSignature(
            "Webhook signature mismatch"
        )


# =========================================================
# Payload parsing
# =========================================================

def parse_webhook_payload(
    raw_body: bytes,
) -> dict[str, Any]:
    """将原始请求内容解析为 JSON 字典。"""
    try:
        payload = json.loads(
            raw_body.decode("utf-8")
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as exc:
        raise ValueError(
            "Webhook body 不是有效 JSON"
        ) from exc

    if not isinstance(payload, dict):
        raise ValueError(
            "Webhook payload 格式错误"
        )

    return payload


def get_webhook_summary(
    event_name: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """从 LemonSqueezy Webhook 中提取订阅关键信息。"""
    meta = payload.get("meta") or {}
    data = payload.get("data") or {}
    attributes = data.get("attributes") or {}
    custom_data = meta.get("custom_data") or {}

    resource_type = data.get("type")
    resource_id = data.get("id")

    subscription_id = (
        resource_id
        if resource_type == "subscriptions"
        else attributes.get("subscription_id")
    )

    return {
        "event_name": event_name,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "status": attributes.get("status"),
        "customer_email": (
            attributes.get("user_email")
            or attributes.get("customer_email")
        ),
        "customer_id": attributes.get("customer_id"),
        "subscription_id": subscription_id,
        "user_id": custom_data.get("user_id"),
        "renews_at": attributes.get("renews_at"),
        "ends_at": attributes.get("ends_at"),
        "trial_ends_at": attributes.get("trial_ends_at"),
        "cancelled": attributes.get("cancelled"),
        "product_id": attributes.get("product_id"),
        "variant_id": attributes.get("variant_id"),
    }


# =========================================================
# Small helpers
# =========================================================

def normalize_text(value: Any) -> Optional[str]:
    if value is None:
        return None

    text = str(value).strip()
    return text or None


def normalize_email(value: Any) -> Optional[str]:
    text = normalize_text(value)
    return text.lower() if text else None


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_future_datetime(value: Optional[str]) -> bool:
    """判断 ISO 时间是否晚于当前 UTC 时间。"""
    if not value:
        return False

    try:
        parsed = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )

        if parsed.tzinfo is None:
            parsed = parsed.replace(
                tzinfo=timezone.utc
            )

        return parsed > datetime.now(
            timezone.utc
        )
    except (TypeError, ValueError):
        return False


def choose_period_end(
    summary: dict[str, Any],
) -> Optional[str]:
    """
    优先使用 ends_at；
    没有 ends_at 时使用 renews_at。
    """
    return (
        normalize_text(summary.get("ends_at"))
        or normalize_text(summary.get("renews_at"))
        or normalize_text(summary.get("trial_ends_at"))
    )


def determine_plan(
    event_name: str,
    status: Optional[str],
    period_end: Optional[str],
) -> str:
    """
    根据订阅事件及状态决定 Mango AI 套餐。

    cancelled 通常表示已取消自动续费，
    用户可能仍可使用到 ends_at，所以在到期前保留 premium。
    """
    normalized_status = (
        status or ""
    ).strip().lower()

    if event_name == "subscription_expired":
        return "free"

    if normalized_status in {
        "expired",
        "unpaid",
    }:
        return "free"

    if normalized_status == "cancelled":
        return (
            "premium"
            if is_future_datetime(period_end)
            else "free"
        )

    if normalized_status in {
        "active",
        "on_trial",
        "paused",
        "past_due",
    }:
        return "premium"

    if event_name in {
        "subscription_created",
        "subscription_resumed",
        "subscription_payment_success",
    }:
        return "premium"

    return "free"


# =========================================================
# User matching
# =========================================================

def resolve_user_id(
    supabase_admin: Client,
    summary: dict[str, Any],
) -> Optional[str]:
    """
    查找付款对应的 Mango AI 用户。

    顺序：
    1. LemonSqueezy meta.custom_data.user_id
    2. device_sessions.email
    3. 已有 user_subscriptions.email
    """
    custom_user_id = normalize_text(
        summary.get("user_id")
    )

    if custom_user_id:
        return custom_user_id

    email = normalize_email(
        summary.get("customer_email")
    )

    if not email:
        return None

    # 尝试从 device_sessions 根据邮箱匹配。
    # 如果当前表没有 email 字段，捕获异常后继续。
    try:
        result = (
            supabase_admin
            .table("device_sessions")
            .select("user_id")
            .eq("email", email)
            .limit(1)
            .execute()
        )

        if result.data:
            user_id = result.data[0].get(
                "user_id"
            )
            if user_id:
                return str(user_id)

    except Exception as exc:
        print(
            "Cannot match user through "
            f"device_sessions.email: {exc}"
        )

    # 尝试从已有订阅记录匹配。
    try:
        result = (
            supabase_admin
            .table("user_subscriptions")
            .select("user_id")
            .eq("email", email)
            .limit(1)
            .execute()
        )

        if result.data:
            user_id = result.data[0].get(
                "user_id"
            )
            if user_id:
                return str(user_id)

    except Exception as exc:
        print(
            "Cannot match user through "
            f"user_subscriptions.email: {exc}"
        )

    return None


# =========================================================
# Database writes
# =========================================================

def save_subscription_record(
    supabase_admin: Client,
    summary: dict[str, Any],
    user_id: str,
    plan: str,
) -> None:
    """
    插入或更新 user_subscriptions。

    当前表只有 id 为主键，因此不能直接依赖 user_id upsert；
    这里先查询，再 update 或 insert。
    """
    email = normalize_email(
        summary.get("customer_email")
    )

    subscription_id = normalize_text(
        summary.get("subscription_id")
    )

    customer_id = normalize_text(
        summary.get("customer_id")
    )

    status = (
        normalize_text(summary.get("status"))
        or "unknown"
    )

    current_period_end = choose_period_end(
        summary
    )

    record = {
        "user_id": user_id,
        "email": email,
        "plan": plan,
        "status": status,
        "lemonsqueezy_customer_id": customer_id,
        "lemonsqueezy_subscription_id": (
            subscription_id
        ),
        "current_period_end": (
            current_period_end
        ),
    }

    # 优先按 LemonSqueezy subscription_id 查找。
    existing_data: list[dict[str, Any]] = []

    if subscription_id:
        existing = (
            supabase_admin
            .table("user_subscriptions")
            .select("id")
            .eq(
                "lemonsqueezy_subscription_id",
                subscription_id,
            )
            .limit(1)
            .execute()
        )
        existing_data = existing.data or []

    # 如果没有匹配订阅 ID，则按 user_id 查找。
    if not existing_data:
        existing = (
            supabase_admin
            .table("user_subscriptions")
            .select("id")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        existing_data = existing.data or []

    if existing_data:
        record_id = existing_data[0]["id"]

        (
            supabase_admin
            .table("user_subscriptions")
            .update(record)
            .eq("id", record_id)
            .execute()
        )

        print(
            "Subscription record updated: "
            f"{record_id}"
        )
    else:
        (
            supabase_admin
            .table("user_subscriptions")
            .insert(record)
            .execute()
        )

        print(
            "Subscription record inserted "
            f"for user {user_id}"
        )


def update_device_session_plan(
    supabase_admin: Client,
    user_id: str,
    plan: str,
) -> None:
    """
    同步现有 device_sessions.plan。

    你的 app.py 当前通过 device_sessions.plan
    判断用户套餐，因此这里必须同步。
    """
    (
        supabase_admin
        .table("device_sessions")
        .update({"plan": plan})
        .eq("user_id", user_id)
        .execute()
    )

    print(
        "Device session plan updated: "
        f"user={user_id}, plan={plan}"
    )


# =========================================================
# Main event processor
# =========================================================

def process_subscription_event(
    event_name: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """
    处理 LemonSqueezy 订阅事件并同步 Supabase。
    """
    supported_events = {
        "subscription_created",
        "subscription_updated",
        "subscription_cancelled",
        "subscription_resumed",
        "subscription_expired",
        "subscription_payment_success",
        "order_created",
        "order_refunded",
    }

    summary = get_webhook_summary(
        event_name=event_name,
        payload=payload,
    )

    if event_name not in supported_events:
        return {
            "processed": False,
            "reason": "event_not_supported",
            "summary": summary,
        }

    # order_created 可能不包含完整订阅状态。
    # 正式升级主要依赖 subscription_created / updated。
    if (
        event_name == "order_created"
        and not summary.get("subscription_id")
    ):
        return {
            "processed": False,
            "reason": "order_has_no_subscription",
            "summary": summary,
        }

    supabase_admin = get_supabase_admin()

    user_id = resolve_user_id(
        supabase_admin=supabase_admin,
        summary=summary,
    )

    if not user_id:
        email = summary.get("customer_email")

        raise WebhookProcessingError(
            "无法确定对应 Mango AI 用户。"
            f" customer_email={email!r}；"
            "请在 Checkout custom_data 中传入 user_id。"
        )

    summary["user_id"] = user_id

    current_period_end = choose_period_end(
        summary
    )

    plan = determine_plan(
        event_name=event_name,
        status=normalize_text(
            summary.get("status")
        ),
        period_end=current_period_end,
    )

    save_subscription_record(
        supabase_admin=supabase_admin,
        summary=summary,
        user_id=user_id,
        plan=plan,
    )

    update_device_session_plan(
        supabase_admin=supabase_admin,
        user_id=user_id,
        plan=plan,
    )

    return {
        "processed": True,
        "user_id": user_id,
        "plan": plan,
        "status": summary.get("status"),
        "subscription_id": summary.get(
            "subscription_id"
        ),
        "summary": summary,
    }