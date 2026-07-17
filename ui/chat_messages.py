import streamlit as st


def render_user_content(content):
    """
    渲染用户消息。

    content 可以是：
    1. 普通字符串
    2. OpenAI 多模态消息列表：
       [
           {"type": "text", "text": "..."},
           {
               "type": "image_url",
               "image_url": {"url": "data:image/..."}
           },
       ]
    """

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
            image_data = item.get("image_url", {})
            image_url = image_data.get("url", "")

            if image_url:
                st.image(image_url)


def render_chat_messages(messages):
    for msg in messages:

        role = msg.get("role", "assistant")
        content = msg.get("content", "")

        if role == "assistant":

            model_name = msg.get("model_name") or "Mango AI"
            model_icon = msg.get("model_icon") or "🤖"

            with st.chat_message(
                "assistant",
                avatar=model_icon,
            ):
                st.caption(model_name)
                st.markdown(content)

        else:
            with st.chat_message("user"):
                render_user_content(content)