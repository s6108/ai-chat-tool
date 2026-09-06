import uuid

from services.cookie_service import (
    get_cookie,
    set_cookie,
    persist_cookies,
)

DEVICE_ID_COOKIE = "megor_device_id"


def get_device_id(cookies) -> str:
    """
    获取当前设备的稳定 device_id。

    优先从第一方 Cookie 读取；
    如果不存在，则生成新的 UUID 并持久化。

    不使用 streamlit_js_eval，
    不创建 iframe，
    避免影响 App 首屏加载速度。
    """

    device_id = get_cookie(
        cookies,
        DEVICE_ID_COOKIE,
    )

    if device_id:
        return str(device_id)

    device_id = str(uuid.uuid4())

    set_cookie(
        cookies,
        DEVICE_ID_COOKIE,
        device_id,
    )

    persist_cookies(cookies)

    return device_id