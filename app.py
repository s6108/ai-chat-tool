import streamlit as st
import os
import base64
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
KIMI_API_KEY = get_key("KIMI_API_KEY")
DOUBAO_API_KEY = get_key("DOUBAO_API_KEY")
DASHSCOPE_API_KEY = get_key("DASHSCOPE_API_KEY")

# ====================== 所有模型 ======================
model_options = {
    "DeepSeek":  {"base_url": "https://api.deepseek.com", "model": "deepseek-chat", "key": DEEPSEEK_API_KEY},
    "GLM-4V":    {"base_url": "https://open.bigmodel.cn/api/paas/v4/", "model": "glm-4v-plus", "key": ZHIPU_API_KEY},
    "GLM-4":     {"base_url": "https://open.bigmodel.cn/api/paas/v4/", "model": "glm-4-plus", "key": ZHIPU_API_KEY},
    "Kimi":      {"base_url": "https://api.moonshot.cn/v1", "model": "moonshot-v1-8k", "key": KIMI_API_KEY},
    "Doubao-Pro":{"base_url": "https://ark.cn-beijing.volces.com/api/v3", "model": "ep-20260415022601-jm5b7", "key": DOUBAO_API_KEY},
    "Qwen":      {"base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen-plus", "key": DASHSCOPE_API_KEY},
}

def auto_select_model(has_image=False, text_length=0):
    if has_image:
        return "GLM-4V"
    if text_length > 800:
        return "Kimi"
    if text_length > 300:
        return "Doubao-Pro"
    return "DeepSeek"

# ====================== 初始化 ======================
if "messages" not in st.session_state:
    st.session_state.messages = []
if "selected_model" not in st.session_state:
    st.session_state.selected_model = "DeepSeek"

# ====================== 侧边栏模型选择 ======================
with st.sidebar:
    st.title("🥭 Mango AI")
    st.markdown("### 模型选择")
    for name in model_options.keys():
        label = "🔴 " + name if st.session_state.selected_model == name else "⚪ " + name
        if st.button(label, key=f"btn_{name}", use_container_width=True):
            st.session_state.selected_model = name
            st.rerun()

# ====================== 主界面 ======================
st.title("🥭 Mango AI")
st.markdown("**智能多模型 · 支持图片与长文本**")

if st.button("🗑️ 清空对话"):
    st.session_state.messages = []
    st.rerun()

# 显示聊天记录
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
prompt = st.chat_input("输入你的问题...")
uploaded_file = st.file_uploader("📎 上传图片", type=["png", "jpg", "jpeg"])

# ====================== 处理输入 ======================
if prompt or uploaded_file is not None:
    text_length = len(prompt) if prompt else 0
    has_image = uploaded_file is not None
    
    st.session_state.selected_model = auto_select_model(has_image, text_length)

    user_content = []
    display_text = prompt or ""

    if uploaded_file:
        b64 = base64.b64encode(uploaded_file.getvalue()).decode()
        user_content.append({"type": "text", "text": display_text or "请描述这张图片"})
        user_content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
        st.image(uploaded_file, caption="✅ 图片已上传")

    if prompt and not uploaded_file:
        user_content.append({"type": "text", "text": prompt})

    st.session_state.messages
