import streamlit as st

st.set_page_config(
    page_title="Mango AI",
    page_icon="🥭",
    layout="centered"
)

# PWA 支持
st.markdown("""
<link rel="manifest" href="/manifest.json">
<meta name="theme-color" content="#FF9800">
""", unsafe_allow_html=True)

# 极简橙色背景
st.markdown("""
<style>
    .main {background: linear-gradient(135deg, #FFF8E1, #FFFCF5) !important;}
    .stButton>button {border-radius: 12px;}
</style>
""", unsafe_allow_html=True)

# 初始化聊天记录
if "messages" not in st.session_state:
    st.session_state.messages = []

# ==================== PWA 安装引导 ====================
st.markdown("""
<div style="text-align: center; margin: 20px 0 25px 0; padding: 20px; 
            background: linear-gradient(135deg, #FFFCF0, #FFE0B2); 
            border-radius: 16px; border: 2px solid #FF9800; box-shadow: 0 4px 12px rgba(255,152,0,0.2);">
    
    <p style="margin: 0 0 8px 0; font-size: 18px; color: #E65100; font-weight: bold;">
        📱 推荐：添加到主屏幕，像原生 App 一样使用
    </p >
    
    <p style="margin: 0 0 16px 0; color: #333; line-height: 1.6; font-size: 15px;">
        <strong>操作步骤：</strong><br>
        1. 点击浏览器右上角 <strong>⋮</strong> 菜单<br>
        2. 选择 <strong>“添加到主屏幕”</strong> 或 <strong>“安装应用”</strong><br>
        3. 点击“添加”即可
    </p >
    
    <div style="background: white; padding: 12px; border-radius: 12px; margin: 12px 0; font-size: 14px;">
        <strong>✅ 添加后好处：</strong><br>
        • 像原生 App 一样打开<br>
        • 关闭时不再白屏<br>
        • 使用更流畅稳定
    </div>
    
    <button onclick="window.alert('请点击浏览器右上角 ⋮ → 选择「添加到主屏幕」或「安装应用」'); return false;" 
            style="background: #FF9800; color: white; border: none; padding: 14px 32px; 
                   border-radius: 50px; font-size: 16px; font-weight: bold; width: 100%; max-width: 280px;">
        📲 我知道了，去添加
    </button>
</div>
""", unsafe_allow_html=True)

# ==================== 主界面 ====================
st.title("🥭 Mango AI")
st.caption("Zhipu + DeepSeek + Kimi + Doubao + Qwen\n低成本 · 高性能 · 连续对话")

# 付费按钮
col1, col2 = st.columns(2)
with col1:
    st.link_button(
        "🚀 升级基础版 ($9.99/月)", 
        "https://yufan-ai-chat.lemonsqueezy.com/checkout/buy/4e54840f-f7b5-4ccb-9051-f193b3a5ea87",
        use_container_width=True
    )
with col2:
    st.link_button(
        "⭐ 升级高级版 ($14.99/月)", 
        "https://yufan-ai-chat.lemonsqueezy.com/checkout/buy/18622988-9cb4-436f-a106-e3db06f8741a",
        use_container_width=True
    )

st.divider()

# 侧边栏
with st.sidebar:
    st.markdown("### 🥭 Mango AI")
    st.caption("多模型 AI 聊天工具")
    model_options = ["DeepSeek", "智谱 GLM-4", "Kimi", "豆包-Pro", "豆包-Lite", "通义千问"]
    selected_model = st.radio("选择模型", model_options, label_visibility="collapsed")
    
    if st.button("🗑️ 清空聊天", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# 聊天记录显示
for msg in st.session_state.messages:
    if msg["role"] == "user":
        st.chat_message("user").markdown(msg["content"])
    else:
        st.chat_message("assistant").markdown(msg["content"])

# 输入框
if prompt := st.chat_input("输入你的问题..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    # 这里你可以后面再加上实际调用 API 的逻辑
    st.session_state.messages.append({"role": "assistant", "content": "这是测试回复（实际调用 API 后会显示真实答案）"})
    st.rerun()

st.caption("Powered by Chinese Multi-Models · Deployed Overseas")
