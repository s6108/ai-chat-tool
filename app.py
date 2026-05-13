import streamlit as st
import os
import base64
import requests
from openai import OpenAI

st.set_page_config(page_title="Mango AI", page_icon="🥭", layout="centered")

st.markdown("""
    <link rel="manifest" href="/manifest.json">
    <meta name="theme-color" content="#ff9800">
""", unsafe_allow_html=True)

# ====================== 密钥 ======================
def get_key(name: str):
    return os.getenv(name) or st.secrets.get(name)

ZHIPU_API_KEY = get_key("ZHIPU_API_KEY")
DEEPSEEK_API_KEY = get_key("DEEPSEEK_API_KEY")
DOUBAO_API_KEY = get_key("DOUBAO_API_KEY")

# ====================== 模型 ======================
model_options = {
    "DeepSeek": {"base_url": "https://api.deepseek.com", "model": "deepseek-chat", "key": DEEPSEEK_API_KEY},
    "GLM-4V": {"base_url": "https://open.bigmodel.cn/api/paas/v4/", "model": "glm-4v-plus", "key": ZHIPU_API_KEY},
}

def auto_select_model(has_image=False):
    return "GLM-4V" if has_image else "DeepSeek"

# ====================== 语音功能暂时关闭（避免500错误） ======================
def doubao_asr(audio_bytes):
    return "🎤 语音识别暂不可用，请使用文字输入"

# ====================== 初始化 ======================
if "messages" not in st.session_state:
    st.session_state.messages = []
if "current_model" not in st.session_state:
    st.session_state.current_model = "DeepSeek"

# ====================== 界面 ======================
st.title("🥭 Mango AI")
st.markdown("**智能自动选择模型 · 支持图像识别**")

if st.button("🗑️ 清空对话"):
    st.session_state.messages = []
    st.rerun()

# 显示历史
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if isinstance(msg["content"], str):
            st.markdown(msg["content"])
        elif isinstance(msg["content"], list):
            for part in msg["content"]:
                if part.get("type") == "text":
                    st.markdown(part.get("text", ""))
                elif part.get("type") == "image_url":
                    st.image(part["image_url"]["url"])

# 输入区域
col1, col2, col3 = st.columns([6, 1, 1])
with col1:
    prompt = st.chat_input("输入你的问题...")

with col2:
    uploaded_file = st.file_uploader("📎", type=["png","jpg","jpeg"], label_visibility="collapsed")

with col3:
    audio_value = st.audio_input("🎤", label_visibility="collapsed")  # 按钮保留，但功能关闭

# 处理输入
if prompt or uploaded_file is not None or audio_value is not None:
    has_image = uploaded_file is not None
    st.session_state.current_model = auto_select_model(has_image)
    
    user_content = []
    display_text = prompt or ""

    if uploaded_file:
        b64 = base64.b64encode(uploaded_file.getvalue()).decode()
        user_content.append({"type": "text", "text": display_text or "描述这张图片"})
        user_content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
        st.image(uploaded_file, caption="✅ 图片已上传")

    if audio_value:
        st.warning("🎤 语音识别暂不可用，请使用文字输入")
        display_text += "\n（语音输入暂不可用）"

    if prompt and not uploaded_file:
        user_content.append({"type": "text", "text": prompt})

    st.session_state.messages.append({"role": "user", "content": user_content or display_text})

    with st.chat_message("user"):
        st.markdown(display_text)

    # AI 回复
    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_response = ""
        try:
            cfg = model_options[st.session_state.current_model]
            client = OpenAI(base_url=cfg["base_url"], api_key=cfg["key"])
            stream = client.chat.completions.create(
                model=cfg["model"],
                messages=[{"role": m["role"], "content": m["content"]} for m in st.session_state.messages],
                stream=True,
                temperature=0.7,
                max_tokens=2000,
            )
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    full_response += chunk.choices[0].delta.content
                    placeholder.markdown(full_response + "▌")
            placeholder.markdown(full_response)
        except Exception as e:
            placeholder.error(f"调用失败: {str(e)}")
            full_response = "抱歉，出错了，请重试。"

        st.session_state.messages.append({"role": "assistant", "content": full_response})

st.caption(f"当前模型: **{st.session_state.current_model}**（自动选择）\n支持图像识别 · 语音识别暂不可用")
