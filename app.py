import streamlit as st

# ==================== 页面配置 ====================
st.set_page_config(
    page_title="Mango AI",
    page_icon="🥭",
    layout="centered",
    initial_sidebar_state="expanded"
)

# ==================== 自定义 CSS 美化（重点修改） ====================
st.markdown("""
<style>
    /* 整体背景 - 极浅橙色 */
    .main {
        background: linear-gradient(135deg, #FFF8E1 0%, #FFFCF5 100%);
    }
    
    /* 升级按钮美化 */
    .stButton > button {
        border-radius: 12px;
        font-weight: bold;
        padding: 12px 20px;
        transition: all 0.3s;
    }
    
    /* 基础版 - 浅橙色 */
    .base-btn {
        background: linear-gradient(90deg, #FFCC33, #FFAA00) !important;
        color: #333 !important;
        border: none !important;
    }
    .base-btn:hover {
        background: linear-gradient(90deg, #FFDD55, #FFBB22) !important;
        transform: translateY(-2px);
    }
    
    /* 高级版 - 深橙色 */
    .premium-btn {
        background: linear-gradient(90deg, #FF7700, #FF5500) !important;
        color: white !important;
        border: none !important;
    }
    .premium-btn:hover {
        background: linear-gradient(90deg, #FF8800, #FF6600) !important;
        transform: translateY(-2px);
    }
    
    /* 聊天气泡优化 */
    .stChatMessage {
        border-radius: 18px;
        padding: 14px 18px;
        margin-bottom: 10px;
    }
    
    /* 用户消息 - 浅橙色 */
    .user-message {
        background: #FFCC33 !important;
        color: #333 !important;
    }
    
    /* AI 消息 - 白色带浅橙边 */
    .assistant-message {
        background: white !important;
        color: #333 !important;
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

# ==================== 主界面 ====================
st.markdown('<h1 class="header-title">🥭 Mango AI</h1>', unsafe_allow_html=True)
st.markdown('<p style="text-align: center; color: #666; font-size: 16px;">Zhipu + DeepSeek + Kimi + Doubao + Qwen<br>低成本 · 高性能 · 连续对话</p >', unsafe_allow_html=True)

# 升级按钮区域（颜色已修改）
col1, col2 = st.columns(2)

with col1:
    if st.button("🚀 升级基础版 ($9.99/月)", key="base", use_container_width=True):
        st.markdown('<a href=" " target="_blank">跳转支付</a >', unsafe_allow_html=True)

with col2:
    if st.button("⭐ 升级高级版 ($14.99/月)", key="premium", use_container_width=True):
        st.markdown('<a href="你的高级版支付链接" target="_blank">跳转支付</a >', unsafe_allow_html=True)

st.divider()

# 聊天记录（会自动应用上面的气泡样式）
for message in st.session_state.messages:
    if message["role"] == "user":
        st.chat_message("user").markdown(message["content"])
    else:
        st.chat_message("assistant").markdown(message["content"])

# 输入框
if prompt := st.chat_input("输入你的问题..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.rerun()

st.caption("Powered by Chinese Multi-Models · Deployed Overseas")
