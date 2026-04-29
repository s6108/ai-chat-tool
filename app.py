import streamlit as st
import os
import base64
from openai import OpenAI

# ==================== PWA 配置 ====================
st.set_page_config(
    page_title="Mango AI",
    page_icon="🥭",
    layout="centered",
)

st.markdown("""
    <link rel="manifest" href="/manifest.json">
    <meta name="theme-color" content="#ff9800">
    """, unsafe_allow_html=True)

# ====================== API Key ======================
def get_key(name: str):
    return os.getenv(name) or st.secrets.get(name)

ZHIPU_API_KEY = get_key("ZHIPU_API_KEY")
DEEPSEEK_API_KEY = get_key("DEEPSEEK_API_KEY")
KIMI_API_KEY = get_key("KIMI_API_KEY")
DOUBAO_API_KEY = get_key("DOUBAO_API_KEY")
DASHSCOPE_API_KEY = get_key("DASHSCOPE_API_KEY")

# ====================== 界面 ======================
st.title("🥭 Mango AI")
st.markdown("**Multi-Model AI Chat Tool** · Vision Supported")

# ====================== 付费按钮（已更新最新链接） ======================
col1, col2 = st.columns(2)
with col1:
    st.link_button("🚀 Basic $9.99/month", 
                   "https://yufan-ai-chat.lemonsqueezy.com/checkout/buy/18622988-9cb4-436f-a106-e3db06f8741a?lang=en", 
                   use_container_width=True)
with col2:
    st.link_button("⭐ Premium $14.99/month", 
                   "https://jjyo-ai-chat.lemonsqueezy.com/checkout/buy/ba6ddc8c-7c6f-40e1-b886-019ebc747a0a?lang=en", 
                   use_container_width=True)

st.divider()

# ====================== 模型选择 ======================
st.subheader("Select Model")

model_options = {
    "DeepSeek": ("https://api.deepseek.com", "deepseek-chat", DEEPSEEK_API_KEY),
    "GLM-4": ("https://open.bigmodel.cn/api/paas/v4/", "glm-4", ZHIPU_API_KEY),
    "GLM-4V": ("https://open.bigmodel.cn/api/paas/v4/", "glm-4v", ZHIPU_API_KEY),
    "Kimi": ("https://api.moonshot.cn/v1", "moonshot-v1-8k", KIMI_API_KEY),
    "Doubao-Pro": ("https://ark.cn-beijing.volces.com/api/v3", "ep-20260415022601-jm5b7", DOUBAO_API_KEY),
    "Doubao-Lite": ("https://ark.cn-beijing.volces.com/api/v3", "ep-20260415023354-lx4bm", DOUBAO_API_KEY),
    "Qwen": ("https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-plus", DASHSCOPE_API_KEY),
}

if "selected_model_name" not in st.session_state:
    st.session_state.selected_model_name = "GLM-4V"
    st.session_state.base_url = model_options["GLM-4V"][0]
    st.session_state.model_name = model_options["GLM-4V"][1]
    st.session_state.api_key = model_options["GLM-4V"][2]

cols = st.columns(len(model_options))
for idx, (name, (url, mdl, key)) in enumerate(model_options.items()):
    with cols[idx]:
        is_selected = st.session_state.selected_model_name == name
        label = "🔴 " + name if is_selected else "⚪ " + name
        if st.button(label, use_container_width=True, key=f"model_{idx}"):
            st.session_state.selected_model_name = name
            st.session_state.base_url = url
            st.session_state.model_name = mdl
            st.session_state.api_key = key
            st.rerun()

st.caption(f"**Current Model:** {st.session_state.selected_model_name}")

st.divider()

# ====================== 聊天记录 ======================
if "messages" not in st.session_state:
    st.session_state.messages = []

if st.button("🗑️ Clear Chat"):
    st.session_state.messages = []
    st.rerun()

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if isinstance(message["content"], str):
            st.markdown(message["content"])
        elif isinstance(message["content"], list):
            for item in message["content"]:
                if isinstance(item, dict) and item.get("type") == "text":
                    st.markdown(item.get("text"))
                elif isinstance(item, dict) and "image_url" in item:
                    st.image(item["image_url"]["url"])

# ====================== 输入区域 ======================
prompt = st.chat_input("Ask anything...")

col_attach, col_voice = st.columns([1, 1])
with col_attach:
    uploaded_file = st.file_uploader("📎", type=["png", "jpg", "jpeg"], label_visibility="collapsed")

with col_voice:
    audio_value = st.audio_input("🎤", label_visibility="collapsed")

if uploaded_file is not None:
    st.image(uploaded_file, width=300)

if audio_value is not None:
    st.audio(audio_value)

# ====================== 发送消息 ======================
if prompt or uploaded_file is not None:
    if uploaded_file is not None and st.session_state.selected_model_name == "GLM-4V":
        bytes_data = uploaded_file.getvalue()
        base64_image = base64.b64encode(bytes_data).decode('utf-8')
        content = [
            {"type": "text", "text": prompt or "Describe this image"},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
        ]
    else:
        content = prompt or "I sent an image."

    st.session_state.messages.append({"role": "user", "content": content})

    with st.chat_message("user"):
        if prompt: st.markdown(prompt)
        if uploaded_file: st.image(uploaded_file, width=300)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_response = ""
        try:
            client = OpenAI(base_url=st.session_state.base_url, api_key=st.session_state.api_key)
            stream = client.chat.completions.create(
                model=st.session_state.model_name,
                messages=st.session_state.messages,
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
            placeholder.error(f"Error: {str(e)}")
            full_response = "Sorry, something went wrong."

    st.session_state.messages.append({"role": "assistant", "content": full_response})

st.caption("由中国主流大模型驱动 · 海外部署\nPowered by Chinese LLMs · Deployed Overseas")
