import streamlit as st
from ui.brand_assets import USER_AVATAR, model_avatar


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


def render_chat_messages(messages):
    for msg in messages:
        role = msg.get("role", "assistant")
        content = msg.get("content", "")
        if role == "assistant":
            model_name = msg.get("model_name") or "Mango AI"
            with st.chat_message("assistant", avatar=model_avatar(model_name)):
                st.caption(model_name)
                st.markdown(content)
        else:
            with st.chat_message("user", avatar=USER_AVATAR):
                render_user_content(content)
