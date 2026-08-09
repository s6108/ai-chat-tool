import os

import streamlit as st
from streamlit_cookies_manager import EncryptedCookieManager


st.set_page_config(
    page_title="Encrypted Cookie Test",
    page_icon="🍪",
)

st.title("🍪 EncryptedCookieManager 最小测试")

password = os.getenv(
    "COOKIE_PASSWORD",
    "megor-local-cookie-test-password-change-me",
)

cookies = EncryptedCookieManager(
    prefix="megor_ai_test_",
    password=password,
)

if not cookies.ready():
    st.info("正在初始化 Cookie 组件，请稍候……")
    st.stop()

COOKIE_NAME = "persistent_cookie"

st.write("当前 Cookie 名称：", list(cookies.keys()))
st.write("测试 Cookie 值：", cookies.get(COOKIE_NAME))

if st.button("写入测试 Cookie"):
    cookies[COOKIE_NAME] = "cookie-is-working"

    if cookies.save():
        st.success("Cookie 已保存。现在按 F5 刷新页面。")
    else:
        st.error("Cookie 保存失败。")

if st.button("删除测试 Cookie"):
    if COOKIE_NAME in cookies:
        del cookies[COOKIE_NAME]

    if cookies.save():
        st.success("Cookie 已删除。现在按 F5 验证。")
    else:
        st.error("Cookie 删除失败。")

st.markdown(
    """
### 测试标准

1. 点击“写入测试 Cookie”。
2. 按 F5 刷新。
3. 刷新后应继续显示 `cookie-is-working`。
4. 点击“删除测试 Cookie”。
5. 再次刷新后，值应恢复为 `None`。
"""
)
