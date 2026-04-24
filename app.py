import streamlit as st
import os
from openai import OpenAI

st.set_page_config(page_title="Mango AI", page_icon="🥭", layout="centered")

# PWA 配置
st.markdown('<link rel="manifest" href="/manifest.json">', unsafe_allow_html=True)

# ====================== API Key ======================
def get_key(name: str):
    key = os.getenv(name) or st.secrets.get(name)
    if key:
        st.caption(f"✅ {name} 已加载")  # 调试用，后面可以删除
    return str(key).strip() if key else None

DASHSCOPE_API_KEY = get_key("DASHSCOPE_API_KEY")

# ====================== 模型配置 ======================
model_options = {
    "通义千问": ("https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-plus", DASHSCOPE_API_KEY),
    # 其他模型...
}

# ====================== 聊天逻辑 ======================
if prompt := st.chat_input("输入你的问题..."):
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        try:
            api_key = DASHSCOPE_API_KEY
            if not api_key:
                raise ValueError("DASHSCOPE_API_KEY 未设置或为空")

            client = OpenAI(
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                api_key=api_key,
                default_headers={"Authorization": f"Bearer {api_key}"}
            )

            stream = client.chat.completions.create(
                model="qwen-plus",
                messages=[{"role": "user", "content": prompt}],
                stream=True,
            )

            full_response = ""
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    full_response += chunk.choices[0].delta.content
                    message_placeholder.markdown(full_response + "▌")
            message_placeholder.markdown(full_response)

        except Exception as e:
            message_placeholder.error(f"通义千问调用失败: {str(e)}")
