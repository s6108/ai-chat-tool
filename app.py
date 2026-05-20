import streamlit as st
import os
import base64
from openai import OpenAI

st.set_page_config(page_title="Mango AI", page_icon="🥭", layout="centered")

st.markdown("""
    <link rel="manifest" href="/manifest.json">
    <meta name="theme-color" content="#ff9800">
    <style>
        .main .block-container {
            padding-bottom: 180px !important;
        }
        .fixed-bottom {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background: white;
            padding: 15px;
            box-shadow: 0 -4px 15px rgba(0,0,0,0.15);
            z-index: 1000;
        }
    </style>
""", unsafe_allow_html=True)

# ====================== 密钥和模型（简化） ======================
def get_key(name: str):
    return os.getenv(name) or st.secrets.get(name)

ZHIPU_API_KEY = get_key("ZHIPU_API_KEY")
DEEPSEEK_API_KEY = get_key("DEEPSEEK_API_KEY")
KIMI_API_KEY = get_key("KIMI_API_KEY")

model_options = {
    "DeepSeek": {"base_url": "https://api.deepseek.com", "model": "deepseek-chat", "key": DEEPSEEK_API_KEY},
    "GLM-4V":   {"base_url": "https://open.bigmodel.cn/api/paas/v4/", "model": "glm-4v-plus", "key": ZHIPU_API_KEY},
    "Kimi":     {"base_url": "https://api.moonshot.cn/v1", "model": "moonshot-v1-8k", "key": KIMI_API_KEY},
}

# ====================== 初始化 ======================
if "messages" not in st.session_state:
    st.session_state.messages = []
if "selected_model" not in st.session_state:
    st.session_state.selected_model = "DeepSeek"

# ====================== 侧边栏 ======================
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

if st.button("🗑️ 清空对话"):
    st.session_state.messages = []
    st.rerun()

# 显示聊天记录
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"] if isinstance(msg["content"], str) else "图片已上传")

# ====================== 固定底部输入栏 ======================
st.markdown('<div class="fixed-bottom">', unsafe_allow_html=True)

col_input, col_plus = st.columns([7, 1])

with col_input:
    prompt = st.chat_input("输入你的问题...")

with col_plus:
    uploaded_file = st.file_uploader("📎", type=["png","jpg","jpeg"], label_visibility="collapsed", key="upload")

st.markdown('</div>', unsafe_allow_html=True)

# ====================== 处理输入 ======================
if prompt or uploaded_file is not None:
    has_image = uploaded_file is not None
    if has_image:
        st.session_state.selected_model = "GLM-4V"

    if uploaded_file:
        st.image(uploaded_file, caption="✅ 图片已上传")
        user_msg = "已上传图片"
    else:
        user_msg = prompt

    st.session_state.messages.append({"role": "user", "content": user_msg})

    with st.chat_message("user"):
        st.write(user_msg)

    with st.chat_message("assistant"):
        st.write(f"这是回复（使用 {st.session_state.selected_model} 模型）")

st.caption(f"当前模型: **{st.session_state.selected_model}**")
