import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta, timezone
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
    """从 LemonSqueezy Webhook 中提取订阅/订单关键信息。"""
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

    first_order_item = (
        attributes.get("first_order_item") or {}
    )

    product_id = (
        attributes.get("product_id")
        or first_order_item.get("product_id")
    )

    variant_id = (
        attributes.get("variant_id")
        or first_order_item.get("variant_id")
    )

    return {
        "event_name": event_name,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "order_id": (
            resource_id
            if resource_type == "orders"
            else attributes.get("order_id")
        ),
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
        "cancelled_at": attributes.get("cancelled_at"),
        "trial_ends_at": attributes.get("trial_ends_at"),
        "cancelled": attributes.get("cancelled"),
        "product_id": product_id,
        "variant_id": variant_id,
        "amount": (
            attributes.get("total")
            if resource_type == "orders"
            else None
        ),
        "currency": attributes.get("currency"),
        "refunded": attributes.get("refunded"),
        "refunded_at": attributes.get("refunded_at"),
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
    根据 LemonSqueezy 订阅事件及状态决定 Megor 套餐。

    cancelled 表示停止自动续费，但在有效期结束前
    仍然保留 Premium；真正 expired 后才降级。
    """
    normalized_event = (
        event_name or ""
    ).strip().lower()

    normalized_status = (
        status or ""
    ).strip().lower()

    # 订阅真正到期，立即降级。
    if normalized_event == "subscription_expired":
        return "free"

    if normalized_status in {
        "expired",
        "unpaid",
    }:
        return "free"

    # 已取消续费，但付费周期尚未结束。
    if normalized_status == "cancelled":
        return (
            "premium"
            if is_future_datetime(period_end)
            else "free"
        )

    # 这些状态下暂时保留 Premium。
    if normalized_status in {
        "active",
        "on_trial",
        "paused",
        "past_due",
    }:
        return "premium"

    # 新建、恢复或付款恢复后启用 Premium。
    if normalized_event in {
        "subscription_created",
        "subscription_resumed",
        "subscription_payment_success",
        "subscription_payment_recovered",
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
    查找付款对应的 Megor 用户。

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

    取消订阅时继续保留 Premium 到 ends_at；
    真正 expired 后才降级为 Free。
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

    event_name = (
        normalize_text(summary.get("event_name"))
        or ""
    ).lower()

    status = (
        normalize_text(summary.get("status"))
        or "unknown"
    ).lower()

    current_period_end = choose_period_end(
        summary
    )

    ends_at = (
        normalize_text(summary.get("ends_at"))
        or None
    )

    cancelled_at = (
        normalize_text(summary.get("cancelled_at"))
        or None
    )

    cancelled = bool(
        summary.get("cancelled")
    )

    # 用户取消：本周期结束前仍然保留 Premium。
    if (
        event_name == "subscription_cancelled"
        or status == "cancelled"
        or cancelled
    ):
        status = "cancelled"
        plan = "premium"

        if not ends_at:
            ends_at = current_period_end

        if not cancelled_at:
            cancelled_at = datetime.now(
                timezone.utc
            ).isoformat()

    # 恢复订阅或付款恢复：重新变成正常 Premium。
    elif (
        event_name in {
            "subscription_resumed",
            "subscription_payment_recovered",
        }
        or status in {
            "active",
            "on_trial",
        }
    ):
        plan = "premium"
        cancelled_at = None
        ends_at = None

    # 真正过期后才降级。
    elif (
        event_name == "subscription_expired"
        or status == "expired"
    ):
        status = "expired"
        plan = "free"

        if not ends_at:
            ends_at = current_period_end

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
        "ends_at": ends_at,
        "cancelled_at": cancelled_at,
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
            f"{record_id}, "
            f"status={status}, "
            f"plan={plan}"
        )
    else:
        (
            supabase_admin
            .table("user_subscriptions")
            .insert(record)
            .execute()
        )

        print(
            "Subscription record inserted: "
            f"user={user_id}, "
            f"status={status}, "
            f"plan={plan}"
        )


def parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def is_30_day_pass_order(
    summary: dict[str, Any],
) -> bool:
    """
    判断一次性订单是否为 Megor 30-Day Pass。

    如果 Render 中配置了 LEMONSQUEEZY_30_DAY_VARIANT_ID
    或 LEMONSQUEEZY_30_DAY_PRODUCT_ID，则严格按配置匹配。

    当前若未配置，则把“没有 subscription_id 的一次性订单”
    视为 30-Day Pass。等拿到 Product/Variant ID 后建议配置环境变量，
    这样以后新增其他一次性产品也不会误判。
    """
    if normalize_text(summary.get("subscription_id")):
        return False

    configured_variant_id = normalize_text(
        os.getenv("LEMONSQUEEZY_30_DAY_VARIANT_ID")
    )
    configured_product_id = normalize_text(
        os.getenv("LEMONSQUEEZY_30_DAY_PRODUCT_ID")
    )

    variant_id = normalize_text(summary.get("variant_id"))
    product_id = normalize_text(summary.get("product_id"))

    if configured_variant_id:
        return variant_id == configured_variant_id

    if configured_product_id:
        return product_id == configured_product_id

    return True


def get_active_pass_expiry(
    supabase_admin: Client,
    user_id: str,
) -> Optional[datetime]:
    result = (
        supabase_admin
        .table("user_passes")
        .select("expires_at")
        .eq("user_id", user_id)
        .eq("status", "active")
        .order("expires_at", desc=True)
        .limit(1)
        .execute()
    )

    if not result.data:
        return None

    return parse_iso_datetime(
        result.data[0].get("expires_at")
    )


def has_active_pass(
    supabase_admin: Client,
    user_id: str,
) -> bool:
    expiry = get_active_pass_expiry(
        supabase_admin=supabase_admin,
        user_id=user_id,
    )
    return bool(
        expiry
        and expiry > datetime.now(timezone.utc)
    )


def has_active_subscription(
    supabase_admin: Client,
    user_id: str,
) -> bool:
    result = (
        supabase_admin
        .table("user_subscriptions")
        .select("plan,status,current_period_end,ends_at")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )

    if not result.data:
        return False

    record = result.data[0]
    plan = (
        normalize_text(record.get("plan"))
        or ""
    ).lower()
    status = (
        normalize_text(record.get("status"))
        or ""
    ).lower()

    if plan != "premium":
        return False

    if status in {
        "active",
        "on_trial",
        "paused",
        "past_due",
    }:
        return True

    if status == "cancelled":
        period_end = (
            normalize_text(record.get("ends_at"))
            or normalize_text(
                record.get("current_period_end")
            )
        )
        return is_future_datetime(period_end)

    return False


def get_effective_plan(
    supabase_admin: Client,
    user_id: str,
) -> str:
    """
    Subscription 或 30-Day Pass 任意一个有效，
    Megor 都应保持 Premium。
    """
    if has_active_subscription(
        supabase_admin=supabase_admin,
        user_id=user_id,
    ):
        return "premium"

    if has_active_pass(
        supabase_admin=supabase_admin,
        user_id=user_id,
    ):
        return "premium"

    return "free"


def save_30_day_pass(
    supabase_admin: Client,
    summary: dict[str, Any],
    user_id: str,
) -> dict[str, Any]:
    """
    为成功的一次性订单增加 30 天 Premium。

    规则：
    - webhook 重复发送不会重复增加天数；
    - 当前 Pass 未到期：从现有 expires_at 继续 +30 天；
    - 当前 Pass 已到期：从现在开始 +30 天。
    """
    order_id = normalize_text(summary.get("order_id"))
    if not order_id:
        raise WebhookProcessingError(
            "30-Day Pass 订单缺少 order_id"
        )

    existing = (
        supabase_admin
        .table("user_passes")
        .select("id,starts_at,expires_at,status")
        .eq("lemonsqueezy_order_id", order_id)
        .limit(1)
        .execute()
    )

    if existing.data:
        record = existing.data[0]
        return {
            "duplicate": True,
            "pass_id": record.get("id"),
            "starts_at": record.get("starts_at"),
            "expires_at": record.get("expires_at"),
            "status": record.get("status"),
        }

    now = datetime.now(timezone.utc)
    current_expiry = get_active_pass_expiry(
        supabase_admin=supabase_admin,
        user_id=user_id,
    )

    starts_at = (
        current_expiry
        if current_expiry and current_expiry > now
        else now
    )
    expires_at = starts_at + timedelta(days=30)

    record = {
        "user_id": user_id,
        "email": normalize_email(
            summary.get("customer_email")
        ),
        "pass_type": "30_day",
        "status": "active",
        "starts_at": starts_at.isoformat(),
        "expires_at": expires_at.isoformat(),
        "lemonsqueezy_order_id": order_id,
        "lemonsqueezy_customer_id": normalize_text(
            summary.get("customer_id")
        ),
        "lemonsqueezy_product_id": normalize_text(
            summary.get("product_id")
        ),
        "lemonsqueezy_variant_id": normalize_text(
            summary.get("variant_id")
        ),
        "amount": summary.get("amount"),
        "currency": normalize_text(
            summary.get("currency")
        ),
        "updated_at": utc_now_iso(),
    }

    inserted = (
        supabase_admin
        .table("user_passes")
        .insert(record)
        .execute()
    )

    pass_id = (
        inserted.data[0].get("id")
        if inserted.data
        else None
    )

    print(
        "30-Day Pass activated: "
        f"user={user_id}, order={order_id}, "
        f"expires_at={expires_at.isoformat()}"
    )

    return {
        "duplicate": False,
        "pass_id": pass_id,
        "starts_at": starts_at.isoformat(),
        "expires_at": expires_at.isoformat(),
        "status": "active",
    }


def recompute_pass_schedule(
    supabase_admin: Client,
    user_id: str,
) -> None:
    """
    退款后重新计算该用户仍有效的一次性购买时间链。

    每一笔未退款 30-Day Pass 都保留 30 天；
    后买的 Pass 会从“购买时间”和“上一张 Pass 到期时间”
    中较晚的时间开始。
    """
    result = (
        supabase_admin
        .table("user_passes")
        .select(
            "id,created_at,starts_at,expires_at,status"
        )
        .eq("user_id", user_id)
        .order("created_at")
        .execute()
    )

    cursor: Optional[datetime] = None

    for row in result.data or []:
        if (
            normalize_text(row.get("status"))
            or ""
        ).lower() != "active":
            continue

        purchased_at = (
            parse_iso_datetime(row.get("created_at"))
            or parse_iso_datetime(row.get("starts_at"))
            or datetime.now(timezone.utc)
        )

        starts_at = (
            max(purchased_at, cursor)
            if cursor is not None
            else purchased_at
        )
        expires_at = starts_at + timedelta(days=30)

        (
            supabase_admin
            .table("user_passes")
            .update({
                "starts_at": starts_at.isoformat(),
                "expires_at": expires_at.isoformat(),
                "updated_at": utc_now_iso(),
            })
            .eq("id", row["id"])
            .execute()
        )

        cursor = expires_at


def refund_30_day_pass(
    supabase_admin: Client,
    summary: dict[str, Any],
) -> dict[str, Any]:
    order_id = normalize_text(summary.get("order_id"))
    if not order_id:
        raise WebhookProcessingError(
            "退款事件缺少 order_id"
        )

    existing = (
        supabase_admin
        .table("user_passes")
        .select("id,user_id,status")
        .eq("lemonsqueezy_order_id", order_id)
        .limit(1)
        .execute()
    )

    if not existing.data:
        return {
            "processed": False,
            "reason": "pass_order_not_found",
        }

    row = existing.data[0]
    user_id = str(row["user_id"])

    if (
        normalize_text(row.get("status"))
        or ""
    ).lower() != "refunded":
        (
            supabase_admin
            .table("user_passes")
            .update({
                "status": "refunded",
                "updated_at": utc_now_iso(),
            })
            .eq("id", row["id"])
            .execute()
        )

        recompute_pass_schedule(
            supabase_admin=supabase_admin,
            user_id=user_id,
        )

    return {
        "processed": True,
        "user_id": user_id,
        "pass_id": row.get("id"),
        "status": "refunded",
    }


def update_device_session_plan(
    supabase_admin: Client,
    user_id: str,
    plan: str,
) -> None:
    """
    同步现有 device_sessions.plan。
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

def process_subscription_event(
    event_name: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """
    处理 LemonSqueezy Subscription + 30-Day Pass 事件并同步 Supabase。
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

    supabase_admin = get_supabase_admin()

    # -----------------------------------------------------
    # 30-Day Pass：一次性购买
    # -----------------------------------------------------
    if (
        event_name == "order_created"
        and not normalize_text(
            summary.get("subscription_id")
        )
    ):
        if not is_30_day_pass_order(summary):
            return {
                "processed": False,
                "reason": "not_30_day_pass",
                "summary": summary,
            }

        user_id = resolve_user_id(
            supabase_admin=supabase_admin,
            summary=summary,
        )

        if not user_id:
            email = summary.get("customer_email")
            raise WebhookProcessingError(
                "无法确定 30-Day Pass 对应的 Megor 用户。"
                f" customer_email={email!r}；"
                "请在 Checkout custom_data 中传入 user_id。"
            )

        summary["user_id"] = user_id

        pass_result = save_30_day_pass(
            supabase_admin=supabase_admin,
            summary=summary,
            user_id=user_id,
        )

        effective_plan = get_effective_plan(
            supabase_admin=supabase_admin,
            user_id=user_id,
        )

        update_device_session_plan(
            supabase_admin=supabase_admin,
            user_id=user_id,
            plan=effective_plan,
        )

        return {
            "processed": True,
            "kind": "30_day_pass",
            "user_id": user_id,
            "plan": effective_plan,
            "pass": pass_result,
            "summary": summary,
        }

    # -----------------------------------------------------
    # 30-Day Pass：退款
    # -----------------------------------------------------
    if (
        event_name == "order_refunded"
        and not normalize_text(
            summary.get("subscription_id")
        )
    ):
        refund_result = refund_30_day_pass(
            supabase_admin=supabase_admin,
            summary=summary,
        )

        if not refund_result.get("processed"):
            return {
                **refund_result,
                "summary": summary,
            }

        user_id = str(refund_result["user_id"])

        effective_plan = get_effective_plan(
            supabase_admin=supabase_admin,
            user_id=user_id,
        )

        update_device_session_plan(
            supabase_admin=supabase_admin,
            user_id=user_id,
            plan=effective_plan,
        )

        return {
            "processed": True,
            "kind": "30_day_pass_refund",
            "user_id": user_id,
            "plan": effective_plan,
            "pass": refund_result,
            "summary": summary,
        }

    # -----------------------------------------------------
    # Subscription
    # -----------------------------------------------------
    # Subscription 的 order_created / order_refunded 不作为主升级事件；
    # 正式状态仍依赖 subscription_created / updated / cancelled / ...
    if event_name in {
        "order_created",
        "order_refunded",
    }:
        return {
            "processed": False,
            "reason": "subscription_order_event_ignored",
            "summary": summary,
        }

    user_id = resolve_user_id(
        supabase_admin=supabase_admin,
        summary=summary,
    )

    if not user_id:
        email = summary.get("customer_email")

        raise WebhookProcessingError(
            "无法确定对应 Megor 用户。"
            f" customer_email={email!r}；"
            "请在 Checkout custom_data 中传入 user_id。"
        )

    summary["user_id"] = user_id

    current_period_end = choose_period_end(
        summary
    )

    subscription_plan = determine_plan(
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
        plan=subscription_plan,
    )

    # 重要：订阅到期/取消后不能直接把设备降为 Free，
    # 因为用户可能同时还有有效 30-Day Pass。
    effective_plan = get_effective_plan(
        supabase_admin=supabase_admin,
        user_id=user_id,
    )

    update_device_session_plan(
        supabase_admin=supabase_admin,
        user_id=user_id,
        plan=effective_plan,
    )

    return {
        "processed": True,
        "kind": "subscription",
        "user_id": user_id,
        "plan": effective_plan,
        "subscription_plan": subscription_plan,
        "status": summary.get("status"),
        "subscription_id": summary.get(
            "subscription_id"
        ),
        "summary": summary,
    }

