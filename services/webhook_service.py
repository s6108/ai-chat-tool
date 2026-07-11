import hashlib
import hmac
import json
import os
from typing import Any


class WebhookConfigurationError(Exception):
    """Webhook 环境变量配置错误。"""


class InvalidWebhookSignature(Exception):
    """Webhook 签名验证失败。"""


def verify_webhook_signature(
    raw_body: bytes,
    received_signature: str,
) -> None:
    """
    验证 LemonSqueezy Webhook 签名。

    验证成功时不返回内容；
    验证失败时抛出异常。
    """
    webhook_secret = os.getenv("LEMONSQUEEZY_WEBHOOK_SECRET")

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


def parse_webhook_payload(raw_body: bytes) -> dict[str, Any]:
    """将原始请求内容解析为 JSON。"""
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Webhook body 不是有效 JSON") from exc

    if not isinstance(payload, dict):
        raise ValueError("Webhook payload 格式错误")

    return payload


def get_webhook_summary(
    event_name: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """
    提取测试阶段需要打印的安全信息。
    暂时不修改 Supabase。
    """
    meta = payload.get("meta") or {}
    data = payload.get("data") or {}
    attributes = data.get("attributes") or {}

    custom_data = meta.get("custom_data") or {}

    return {
        "event_name": event_name,
        "resource_type": data.get("type"),
        "resource_id": data.get("id"),
        "status": attributes.get("status"),
        "customer_email": attributes.get("user_email"),
        "customer_id": attributes.get("customer_id"),
        "subscription_id": (
            data.get("id")
            if data.get("type") == "subscriptions"
            else attributes.get("subscription_id")
        ),
        "user_id": custom_data.get("user_id"),
    }