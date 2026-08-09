import html

import streamlit as st

from ui.brand_assets import USER_AVATAR, model_avatar

import re


def clean_repeated_speaker_label(
    content: str,
    model_name: str,
) -> str:
    """只删除回答开头一个或多个重复的模型发言标签。"""
    if not content or not model_name:
        return content

    escaped_name = re.escape(model_name)

    pattern = (
        rf"^\s*(?:"
        rf"[【\[]\s*{escaped_name}\s*的?\s*(?:发言|观点|回答)\s*[】\]]"
        rf"|{escaped_name}\s*的?\s*(?:发言|观点|回答)\s*[:：]?"
        rf")\s*"
    )

    cleaned = content

    # 连续删除多个重复标签
    while re.match(pattern, cleaned, flags=re.IGNORECASE):
        cleaned = re.sub(
            pattern,
            "",
            cleaned,
            count=1,
            flags=re.IGNORECASE,
        )

    return cleaned.lstrip()


def render_user_content(content):
    if isinstance(content, str):
        st.markdown(content)
        return

    if not isinstance(content, list):
        st.write(content)
        return

    for item in content:
        if not isinstance(item, dict):
            continue

        item_type = item.get("type")

        if item_type == "text":
            text = item.get("text", "")
            if text:
                st.markdown(text)

        elif item_type == "image_url":
            image_url = item.get("image_url", {}).get("url", "")
            if image_url:
                st.image(image_url)


def render_model_title(model_name: str) -> None:
    safe_name = html.escape(model_name or "Megor")
    st.markdown(
        f'<div class="megor-model-title">{safe_name}</div>',
        unsafe_allow_html=True,
    )


def render_chat_messages(messages):
    for msg in messages:
        role = msg.get("role", "assistant")
        content = msg.get("content", "")

        if role == "assistant":
            model_name = msg.get("model_name") or "Megor"

            with st.chat_message(
                "assistant",
                avatar=model_avatar(model_name),
            ):
                render_model_title(model_name)
                st.markdown(content)

        else:
            with st.chat_message("user", avatar=USER_AVATAR):
                render_user_content(content)

