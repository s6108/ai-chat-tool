import os
from typing import Optional

from streamlit_cookies_manager import EncryptedCookieManager


COOKIE_PREFIX = "mango_ai_"


def create_cookie_manager() -> EncryptedCookieManager:
    """创建 Mango AI 唯一的加密 Cookie 管理器。"""
    password = os.getenv("COOKIE_PASSWORD", "").strip()

    if not password:
        # 仅用于本地开发；Render 必须配置 COOKIE_PASSWORD。
        password = "mango-ai-local-cookie-password"

    return EncryptedCookieManager(
        prefix=COOKIE_PREFIX,
        password=password,
    )


def cookies_ready(
    cookies: EncryptedCookieManager,
) -> bool:
    """等待前端 Cookie 组件完成初始化。"""
    try:
        return cookies.ready()
    except Exception as error:
        print(f"CookieManager 初始化失败：{error}")
        return False


def get_cookie(
    cookies: EncryptedCookieManager,
    name: str,
    default: Optional[str] = None,
) -> Optional[str]:
    """读取一个 Cookie，但不触发保存组件。"""
    try:
        value = cookies.get(name)

        if value in (None, ""):
            return default

        return str(value)

    except Exception as error:
        print(f"读取 Cookie {name} 失败：{error}")
        return default


def set_cookie(
    cookies: EncryptedCookieManager,
    name: str,
    value: str,
) -> None:
    """
    只修改内存中的 Cookie。

    注意：这里绝对不能调用 cookies.save()，
    否则同一次 Streamlit 运行中写入多个 Cookie 时会发生组件 key 冲突。
    """
    cookies[name] = value


def delete_cookie(
    cookies: EncryptedCookieManager,
    name: str,
) -> None:
    """只修改内存状态，不在这里调用 save()。"""
    if name in cookies:
        del cookies[name]


def persist_cookies(
    cookies: EncryptedCookieManager,
) -> None:
    """
    把本轮所有 Cookie 修改一次性同步到浏览器。

    cookies.save() 成功时通常返回 None，
    因此不要用 if cookies.save() 判断成功与否。
    """
    cookies.save()
