import streamlit as st

st.set_page_config(
    page_title="Mango AI",
    page_icon="🥭",
    layout="centered",
    initial_sidebar_state="expanded"
)

# ==================== CSS 美化 ====================
st.markdown("""
<style>
    .main {
        background: linear-gradient(135deg, #FFF8E1 0%, #FFFCF5 100%) !important;
    }
    
    .custom-btn {
        border: none !important;
        border-radius: 12px !important;
        padding: 14px 24px !important;
        font-size: 16px !important;
        font-weight: bold !important;
        width: 100% !important;
        margin: 8px 0 !important;
        cursor: pointer !important;
        transition: all 0.3s !important;
    }
    
    .base-btn {
        background: linear-gradient(90deg, #FFCC33, #FFAA00) !important;
        color: #333 !important;
        box-shadow: 0 4px 15px rgba(255, 204, 51, 0.4) !important;
    }
    .base-btn:hover {
        background: linear-gradient(90deg, #FFDD55, #FFBB22) !important;
    }
    
    .premium-btn {
        background: linear-gradient(90deg, #FF7700, #FF5500) !important;
        color: white !important;
        box-shadow: 0 4px 15px rgba(255, 119, 0, 0.5) !important;
    }
    .premium-btn:hover {
        background: linear-gradient(90deg, #FF8800, #FF6600) !important;
    }
</style>
""", unsafe_allow_html=True)

# ==================== 初始化 ====================
if "messages" not in st.session_state:
    st.session_state.messages = []

# ==================== 侧边栏 ====================
with st.sidebar:
    st.markdown("### 🥭 Mango AI")
    st.caption("多模型 AI 聊天工具")
    
    model_options = [
        "DeepSeek",
        "智谱 GLM-4",
        "Kimi",
        "豆包-Pro",
        "豆包-Lite",
        "通义千问"
    ]
    selected_model = st.radio("选择模型", model_options, label_visibility="collapsed")
    
    st.divider()
    if st.button("🗑️ 清空聊天", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# ==================== 主界面 ====================
st.markdown('<h1 style="text-align: center; color: #FF9800;">🥭 Mango AI</h1>', unsafe_allow_html=True)
st.markdown('<p style="text-align: center; color: #666;">Zhipu + DeepSeek + Kimi + Doubao + Qwen<br>低成本 · 高性能 · 连续对话</p >', unsafe_allow_html=True)

# ==================== 升级按钮（使用 JS 强制外部浏览器打开） ====================
col1, col2 = st.columns(2)

with col1:
    st.markdown(f'''
        <a href=" " target="_blank" 
           onclick="window.open(this.href, '_system'); return false;"
           style="text-decoration: none;">
            <button class="custom-btn base-btn">🚀 升级基础版 ($9.99/月)</button>
        </a >
    ''', unsafe_allow_html=True)

with col2:
    st.markdown(f'''
        <a href="你的高级版支付链接" target="_blank" 
           onclick="window.open(this.href, '_system'); return false;"
           style="text-decoration: none;">
            <button class="custom-btn premium-btn">⭐ 升级高级版 ($14.99/月)</button>
        </a >
    ''', unsafe_allow_html=True)

st.divider()

# ==================== 聊天区 ====================
for msg in st.session_state.messages:
    if msg["role"] == "user":
        st.chat_message("user").markdown(msg["content"])
    else:
        st.chat_message("assistant").markdown(msg["content"])

if prompt := st.chat_input("输入你的问题..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.rerun()

st.caption("Powered by Chinese Multi-Models · Deployed Overseas")
