import streamlit as st
from openai import OpenAI
import os

# ==================== 页面配置 ====================
st.set_page_config(
    page_title="Mango AI",
    page_icon="🥭",
    layout="centered",
    initial_sidebar_state="expanded"
)

# ==================== 自定义 CSS 美化 ====================
st.markdown("""
<style>
    .main {background: linear-gradient(135deg, #FFF8E1 0%, #FFFFFF 100%);}
    .stChatMessage {border-radius: 18px; padding: 12px 16px;}
    .user-message {background: #FF9800 !important; color: white !important;}
    .assistant-message {background: #F1F1F1 !important; color: #333 !important;}
    
    .header-title {
        font-size: 28px;
        font-weight: bold;
        background: linear-gradient(90deg, #FF9800, #FF6600);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    .upgrade-btn {
        border-radius: 12px;
        font-weight: bold;
        padding: 12px 20px;
        transition: all 0.3s;
    }
    .upgrade-btn:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 20px rgba(255, 152, 0, 0.3);
    }
</style>
""", unsafe_allow_html=True)

# ==================== 初始化 ====================
if "messages" not in st.session_state:
    st.session_state.messages = []
if "is_premium" not in st.session_state:
    st.session_state.is_premium = False
if "daily_tokens" not in st.session_state:
    st.session_state.daily_tokens = 0

# ==================== 侧边栏 ====================
with st.sidebar:
    st.image("https://your-mango-icon-url.com/icon.png", width=80)  # 可替换成你的图标链接
    st.markdown('<p class="header-title">🥭 Mango AI</p >', unsafe_allow_html=True)
    st.caption("多模型 AI 聊天工具")

    model_options = {
        "DeepSeek": "deepseek-chat",
        "智谱 GLM-4": "glm-4",
        "Kimi": "moonshot-v1-8k",
        "豆包-Pro": "Doubao-Seed-2.0-pro",
        "通义千问": "qwen-max"
    }
    
    selected_model = st.selectbox("选择模型", list(model_options.keys()))
    
    st.divider()
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🗑️ 清空聊天", use_container_width=True):
            st.session_state.messages = []
            st.rerun()
    
    st.caption(f"今日已用: {st.session_state.daily_tokens} tokens")

# ==================== 主界面 ====================
st.markdown('<h1 style="text-align: center; color: #FF9800;">🥭 Mango AI</h1>', unsafe_allow_html=True)
st.markdown('<p style="text-align: center; color: #666;">Zhipu + DeepSeek + Kimi + Doubao + Qwen<br>低成本 · 高性能 · 连续对话</p >', unsafe_allow_html=True)

# 付费升级区域
col1, col2 = st.columns(2)
with col1:
    if st.button("🚀 升级基础版 ($9.99/月)", type="primary", use_container_width=True):
        st.markdown('<a href=" " target="_blank">跳转支付</a >', unsafe_allow_html=True)

with col2:
    if st.button("⭐ 升级高级版 ($14.99/月)", use_container_width=True):
        st.markdown('<a href="你的高级版支付链接" target="_blank">跳转支付</a >', unsafe_allow_html=True)

st.divider()

# 聊天记录
for message in st.session_state.messages:
    if message["role"] == "user":
        st.chat_message("user", avatar="🧑").markdown(message["content"])
    else:
        st.chat_message("assistant", avatar="🥭").markdown(message["content"])

# 输入框
if prompt := st.chat_input("输入你的问题..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.chat_message("user", avatar="🧑").markdown(prompt)
    
    with st.chat_message("assistant", avatar="🥭"):
        with st.spinner("思考中..."):
            # 这里放你的实际调用代码（保持你原来的 API 调用逻辑）
            response = "这是测试回复，实际代码中请替换为你的模型调用逻辑。"
            st.markdown(response)
            st.session_state.messages.append({"role": "assistant", "content": response})

# 页脚
st.caption("Powered by Chinese Multi-Models · Deployed Overseas")
