import json
import os
from typing import Any, Optional

import streamlit as st

COOKIE_PREFIX = "megor_ai_"
_PENDING_KEY = "_megor_pending_cookie_changes"


def create_cookie_manager() -> None:
    """兼容旧调用；不再创建 iframe Cookie 组件。"""
    return None


def cookies_ready(cookies: Any = None) -> bool:
    """原生页面 Cookie 无需等待自定义组件初始化。"""
    return True


def _full_name(name: str) -> str:
    return f"{COOKIE_PREFIX}{name}"


def get_cookie(cookies: Any, name: str, default: Optional[str] = None) -> Optional[str]:
    """从本次浏览器初始请求中读取第一方 Cookie。"""
    try:
        value = st.context.cookies.get(_full_name(name))
        if value in (None, ""):
            return default
        return str(value)
    except Exception as error:
        print(f"读取 Cookie {name} 失败：{error}")
        return default


def _pending() -> dict:
    if _PENDING_KEY not in st.session_state:
        st.session_state[_PENDING_KEY] = {}
    return st.session_state[_PENDING_KEY]


def set_cookie(cookies: Any, name: str, value: str) -> None:
    """暂存 Cookie 写入，persist_cookies() 时一次性写入主页面。"""
    _pending()[name] = str(value)


def delete_cookie(cookies: Any, name: str) -> None:
    """暂存 Cookie 删除。"""
    _pending()[name] = None


def persist_cookies(cookies: Any = None) -> None:
    """
    通过 st.html 在主页面上下文写第一方 Cookie。

    不使用 iframe，因此不会触发 iPhone Safari 对组件 iframe 存储的限制。
    remember_token 是高强度随机不透明令牌；数据库只保存其哈希。
    """
    changes = dict(_pending())
    st.session_state[_PENDING_KEY] = {}

    if not changes:
        return

    secure = os.getenv("RENDER", "").lower() in {"true", "1", "yes"} or bool(
        os.getenv("RENDER_SERVICE_ID")
    )
    secure_part = "; Secure" if secure else ""

    lines = []
    for name, value in changes.items():
        cookie_name = json.dumps(_full_name(name))
        if value is None:
            lines.append(
                f'document.cookie = {cookie_name} + "=; Path=/; Max-Age=0; SameSite=Lax{secure_part}";'
            )
        else:
            encoded_value = json.dumps(str(value))
            lines.append(
                f'document.cookie = {cookie_name} + "=" + encodeURIComponent({encoded_value}) '
                f'+ "; Path=/; Max-Age=2592000; SameSite=Lax{secure_part}";'
            )

    script = "<script>" + "\n".join(lines) + "</script>"
    st.html(script, unsafe_allow_javascript=True)
