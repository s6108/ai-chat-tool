import os
from typing import Optional

import requests


LEMONSQUEEZY_API_BASE_URL = (
    "https://api.lemonsqueezy.com/v1"
)


def get_customer_portal_url(
    subscription_id: Optional[str],
) -> Optional[str]:
    """
    根据 Lemon Squeezy subscription_id 获取临时客户门户链接。

    返回值：
    - 成功：Customer Portal URL
    - 失败或没有订阅：None
    """
    if not subscription_id:
        return None

    api_key = os.getenv("LEMONSQUEEZY_API_KEY")

    if not api_key:
        print(
            "Customer portal unavailable: "
            "LEMONSQUEEZY_API_KEY is missing."
        )
        return None

    url = (
        f"{LEMONSQUEEZY_API_BASE_URL}"
        f"/subscriptions/{subscription_id}"
    )

    headers = {
        "Accept": "application/vnd.api+json",
        "Content-Type": "application/vnd.api+json",
        "Authorization": f"Bearer {api_key}",
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=15,
        )
        response.raise_for_status()

        payload = response.json()

        attributes = (
            payload
            .get("data", {})
            .get("attributes", {})
        )

        portal_url = (
            attributes
            .get("urls", {})
            .get("customer_portal")
        )

        if not portal_url:
            print(
                "Customer portal URL was not returned "
                f"for subscription {subscription_id}."
            )
            return None

        return str(portal_url)

    except requests.RequestException as exc:
        print(
            "Lemon Squeezy portal request failed: "
            f"{exc}"
        )
        return None

    except (TypeError, ValueError) as exc:
        print(
            "Invalid Lemon Squeezy API response: "
            f"{exc}"
        )
        return None