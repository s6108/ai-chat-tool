import streamlit as st
from i18n import LANGUAGE_OPTIONS, language_label, set_language, t


def render_language_selector(cookies=None, key="sidebar_language"):
    labels = list(LANGUAGE_OPTIONS.keys())
    current = language_label(st.session_state.get("language", "en"))
    selected = st.selectbox(
        "🌐 " + t("language_label"),
        labels,
        index=labels.index(current),
        key=key,
    )
    language = LANGUAGE_OPTIONS[selected]
    if language != st.session_state.get("language"):
        set_language(language, cookies)
        if st.session_state.get("auto_mode", True):
            st.session_state.model_selector = t("auto_mode")
        else:
            st.session_state.model_selector = st.session_state.get("selected_model", "DeepSeek")
        st.rerun()


def render_sidebar_placeholder():
    return None
