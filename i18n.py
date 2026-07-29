from __future__ import annotations
from typing import Any
import streamlit as st
from locales.en import TEXT as EN
from locales.zh_CN import TEXT as ZH_CN
from services.cookie_service import get_cookie, set_cookie, persist_cookies

LANGUAGE_COOKIE = "language"
SUPPORTED = {"en": EN, "zh-CN": ZH_CN}
LANGUAGE_OPTIONS = {"English": "en", "简体中文": "zh-CN"}


def _browser_language() -> str:
    try:
        locale = str(st.context.locale or "").lower()
    except Exception:
        locale = ""
    return "zh-CN" if locale.startswith("zh") else "en"


def initialize_language(cookies: Any = None) -> str:
    if "language" not in st.session_state:
        saved = get_cookie(cookies, LANGUAGE_COOKIE)
        st.session_state.language = saved if saved in SUPPORTED else _browser_language()
    return st.session_state.language


def set_language(language: str, cookies: Any = None) -> None:
    if language not in SUPPORTED:
        language = "en"
    st.session_state.language = language
    set_cookie(cookies, LANGUAGE_COOKIE, language)
    persist_cookies(cookies)


def t(key: str, **kwargs: Any) -> str:
    language = st.session_state.get("language", "en")
    value = SUPPORTED.get(language, EN).get(key, EN.get(key, key))
    try:
        return value.format(**kwargs)
    except (KeyError, ValueError):
        return value


def language_label(language: str) -> str:
    return "简体中文" if language == "zh-CN" else "English"