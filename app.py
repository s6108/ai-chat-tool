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

# ====================== 智能模型路由 ======================
def auto_select_model(prompt: str, has_image: bool = False):
    text = prompt.lower() if prompt else ""
    
    # 1. 图像任务 - 优先使用 GLM-4V
    if has_image or any(k in text for k in ["图片", "图像", "照片", "describe", "看图", "what is in"]):
        return "GLM-4V", "https://open.bigmodel.cn/api/paas/v4/", "glm-4v", ZHIPU_API_KEY
    
    # 2. 复杂推理、编程、数学、深度分析
    if any(k in text for k in ["代码", "编程", "写代码", "算法", "reason", "分析", "总结", "数学", "prove"]):
        return "DeepSeek", "https://api.deepseek.com", "deepseek-chat", DEEPSEEK_API_KEY
    
    # 3. 通用对话、创意写作、日常问题
    return "GLM-4", "https://open.bigmodel.cn/api/paas/v4/", "glm-4", ZHIPU_API_KEY


# ====================== 界面 ======================
st.title("🥭 Mango AI")
st.markdown("**Intelligent Multi-Model AI** · Smart Routing")

# 付费按钮
col1, col2 = st.columns(2)
with col1:
    st.link_button("🚀 Basic $9.99/month", 
                   "https://yufan-ai-chat.lemonsqueezy.com/checkout/buy/18622988-9cb4-436f-a106-e3db06f8741a?lang=en&locale=en", 
                   use_container_width=True)
with col2:
    st.link_button("⭐ Premium $14.99/month", 
                   "https://jjyo-ai-chat.lemonsqueezy.com/checkout/buy/ba6ddc8c-7c6f-40e1-b886-019ebc747a0a?lang=en&locale=en", 
                   use_container_width=True)

st.divider()

# ====================== 聊天记录 ======================
if "messages" not in st.session_state:
    st.session_state.messages = []

if st.button("🗑️ Clear Chat"):
    st.session_state.messages = []
    st.rerun()

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if isinstance(msg["content"], str):
            st.markdown(msg["content"])
        elif isinstance(msg["content"], list):
            for part in msg["content"]:
                if isinstance(part, dict) and part.get("type") == "text":
                    st.markdown(part.get("text"))
                elif isinstance(part, dict) and "image_url" in part:
                    st.image(part["image_url"]["url"])

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

# ====================== 发送消息（智能路由） ======================
if prompt or uploaded_file is not None:
    # 自动选择模型
    model_name, base_url, api_model, api_key = auto_select_model(prompt, has_image=uploaded_file is not None)

    # 构建消息
    if uploaded_file is not None and model_name == "GLM-4V":
        bytes_data = uploaded_file.getvalue()
        base64_image = base64.b64encode(bytes_data).decode('utf-8')
        content = [
            {"type": "text", "text": prompt or "请详细描述这张图片"},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
        ]
    else:
        content = prompt or "请描述这张图片"

    st.session_state.messages.append({"role": "user", "content": content})

    with st.chat_message("user"):
        if prompt: st.markdown(prompt)
        if uploaded_file: st.image(uploaded_file, width=300)

    # AI 回复
    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_response = ""
        try:
            client = OpenAI(base_url=base_url, api_key=api_key)
            stream = client.chat.completions.create(
                model=api_model,
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
            placeholder.error(f"调用失败: {str(e)}")
            full_response = "抱歉，当前模型处理出现问题，请稍后再试。"

    st.session_state.messages.append({"role": "assistant", "content": full_response})

st.caption("由中国主流大模型驱动 · 智能路由 · 海外部署\nPowered by Chinese LLMs · Smart Routing")
