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

def _get_document_display_content(content):
    """
    如果 content 是 Megor 文件理解生成的文档消息，
    返回适合聊天界面显示的紧凑文件卡片文字。

    普通消息返回 None。
    """

    if not isinstance(content, str):
        return None

    prefix = 'The user uploaded a file named "'
    file_start = "===== FILE CONTENT ====="
    file_end = "===== END FILE CONTENT ====="
    request_marker = "User request:"

    # 必须同时包含这些标记，避免误判普通聊天内容
    if (
        not content.startswith(prefix)
        or file_start not in content
        or file_end not in content
    ):
        return None

    # 提取文件名
    remaining = content[len(prefix):]
    quote_pos = remaining.find('"')

    if quote_pos == -1:
        return None

    filename = remaining[:quote_pos].strip()

    # 提取用户真正输入的问题
    user_request = ""

    if request_marker in content:
        user_request = (
            content
            .split(request_marker, 1)[1]
            .strip()
        )

    display_text = f"📄 **{filename}**"

    if user_request:
        display_text += f"\n\n{user_request}"

    return display_text

def render_user_content(content):
    document_display = _get_document_display_content(
        content
    )

    if document_display is not None:
        st.markdown(document_display)
        return
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

