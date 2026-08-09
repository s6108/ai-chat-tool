from datetime import datetime, timedelta

import streamlit as st
from streamlit_cookies_controller import CookieController


st.set_page_config(
    page_title="Cookie Test",
    page_icon="🍪",
)

st.title("🍪 Cookie 最小测试")

if "cookie_controller" not in st.session_state:
    st.session_state.cookie_controller = CookieController()

cookies = st.session_state.cookie_controller

COOKIE_NAME = "megor_cookie_test"

try:
    all_cookies = cookies.getAll() or {}
except Exception as error:
    all_cookies = {}
    st.error(f"getAll() 失败：{error}")

st.write("当前 Cookie 名称：", list(all_cookies.keys()))
st.write("测试 Cookie 值：", cookies.get(COOKIE_NAME))

if st.button("写入测试 Cookie"):
    expires = datetime.now() + timedelta(days=30)

    try:
        cookies.set(
            COOKIE_NAME,
            "cookie-is-working",
            expires=expires,
        )
        st.success("已经调用 cookies.set()。等待两秒后按 F5。")
    except Exception as error:
        st.error(f"写入失败：{error}")

if st.button("删除测试 Cookie"):
    try:
        cookies.remove(COOKIE_NAME)
        st.success("已调用删除。")
    except Exception as error:
        st.error(f"删除失败：{error}")