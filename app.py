import streamlit as st
import os
import base64
from openai import OpenAI

st.set_page_config(page_title="Mango AI", page_icon="🥭", layout="centered")

# ====================== 密钥 ======================
def get_key(name: str):
    return os.getenv(name) or st.secrets.get(name)

ZHIPU_API_KEY = get_key("ZHIPU_API_KEY")
DEEPSEEK_API_KEY = get_key("DEEPSEEK_API_KEY")
KIMI_API_KEY = get_key("KIMI_API_KEY")
DOUBAO_API_KEY = get_key("DOUBAO_API_KEY")
DASHSCOPE_API_KEY = get_key("DASHSCOPE_API_KEY")

# ====================== 模型 ======================
model_options = {
    "DeepSeek":  {"base_url": "https://api.deepseek.com", "model": "deepseek-chat", "key": DEEPSEEK_API_KEY},
    "GLM-4V":    {"base_url": "https://open.bigmodel.cn/api/paas/v4/", "model": "glm-4v-plus", "key": ZHIPU_API_KEY},
    "Kimi":      {"base_url": "https://api.moonshot.cn/v1", "model": "moonshot-v1-8k", "key": KIMI_API_KEY},
    "Doubao-Pro":{"base_url": "https://ark.cn-beijing.volces.com/api/v3", "model": "ep-20260415022601-jm5b7", "key": DOUBAO_API_KEY},
    "Qwen":      {"base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen-plus", "key": DASHSCOPE_API_KEY},
}

def auto_select_model(has_image=False):
    return "GLM-4V" if has_image else "DeepSeek"

# ====================== 初始化 ======================
if "messages" not in st.session_state:
    st.session_state.messages = []
if "selected_model" not in st.session_state:
    st.session_state.selected_model = "DeepSeek"

# ====================== 侧边栏 ======================
with st.sidebar:
    st.title("🥭 Mango AI")
    st.markdown("### 💎 升级会员")
    col1, col2 = st.columns(2)
    with col1:
        st.link_button("🚀 基础版 $9.99", "https://yufan-ai-chat.lemonsqueezy.com/checkout/buy/18622988-9cb4-436f-a106-e3db06f8741a?lang=en")
    with col2:
        st.link_button("🔥 高级版 $14.99", "https://jjyo-ai-chat.lemonsqueezy.com/checkout/buy/ba6ddc8c-7c6f-40e1-b886-019ebc747a0a?lang=en")

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

# ====================== 输入区域（+号 + 输入框） ======================
col_input, col_plus = st.columns([6, 1])

with col_input:
    prompt = st.chat_input("输入你的问题...")

with col_plus:
    uploaded_file = st.file_uploader("📎", type=["png","jpg","jpeg"], label_visibility="collapsed")

# ====================== 处理 ======================
if prompt or uploaded_file:
    has_image = uploaded_file is not None
    st.session_state.selected_model = auto_select_model(has_image)

    if uploaded_file:
        st.image(uploaded_file, caption="✅ 图片已上传")
        user_msg = "已上传图片"
    else:
        user_msg = prompt

    st.session_state.messages.append({"role": "user", "content": user_msg})

    with st.chat_message("user"):
        st.write(user_msg)

    with st.chat_message("assistant"):
        st.write("这是测试回复 - 模型调用正常（当前使用：" + st.session_state.selected_model + "）")

st.caption(f"当前模型: **{st.session_state.selected_model}**")
