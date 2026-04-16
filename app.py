import streamlit as st

st.set_page_config(
    page_title="Mango AI",
    page_icon="🥭",
    layout="centered",
    initial_sidebar_state="expanded"
)

# ==================== CSS 美化（重点修复） ====================
st.markdown("""
<style>
    .main {
        background: linear-gradient(135deg, #FFF8E1 0%, #FFFCF5 100%);
    }
    
    /* 升级按钮 - 基础版浅橙色 */
    .stButton button[key="base"] {
        background: linear-gradient(90deg, #FFCC33, #FFAA00) !important;
        color: #333 !important;
        font-weight: bold;
        border-radius: 12px;
        border: none !important;
    }
    .stButton button[key="base"]:hover {
        background: linear-gradient(90deg, #FFDD55, #FFBB22) !important;
    }
    
    /* 升级按钮 - 高级版深橙色 */
    .stButton button[key="premium"] {
        background: linear-gradient(90deg, #FF7700, #FF5500) !important;
        color: white !important;
        font-weight: bold;
        border-radius: 12px;
        border: none !important;
    }
    .stButton button[key="premium"]:hover {
        background: linear-gradient(90deg, #FF8800, #FF6600) !important;
    }
    
    /* 聊天气泡 */
    .stChatMessage {
        border-radius: 18px;
        padding: 14px 18px;
    }
    .user-message {
        background: #FFCC33 !important;
        color: #333 !important;
    }
    .assistant-message {
        background: white !important;
        border: 1px solid #FFEECC;
    }
    
    .header-title {
        font-size: 32px;
        font-weight: bold;
        color: #FF9800;
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

# ==================== 侧边栏 - 恢复模型选择 ====================
with st.sidebar:
    st.markdown("### 🥭 Mango AI")
    st.caption("多模型 AI 聊天工具")
    
    model_options = ["DeepSeek", "智谱 GLM-4", "Kimi", "豆包-Pro", "通义千问"]
    selected_model = st.radio("选择模型", model_options, label_visibility="collapsed")
    
    st.divider()
    if st.button("🗑️ 清空聊天", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# ==================== 主界面 ====================
st.markdown('<h1 class="header-title" style="text-align: center;">🥭 Mango AI</h1>', unsafe_allow_html=True)
st.markdown('<p style="text-align: center; color: #666;">Zhipu + DeepSeek + Kimi + Doubao + Qwen<br>低成本 · 高性能 · 连续对话</p >', unsafe_allow_html=True)

# 升级按钮（使用 key 来精准控制颜色）
col1, col2 = st.columns(2)

with col1:
    st.button("🚀 升级基础版 ($9.99/月)", key="base", use_container_width=True)

with col2:
    st.button("⭐ 升级高级版 ($14.99/月)", key="premium", use_container_width=True)

st.divider()

# 聊天区
for msg in st.session_state.messages:
    if msg["role"] == "user":
        st.chat_message("user").markdown(msg["content"])
    else:
        st.chat_message("assistant").markdown(msg["content"])

if prompt := st.chat_input("输入你的问题..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.rerun()

st.caption("Powered by Chinese Multi-Models · Deployed Overseas")
