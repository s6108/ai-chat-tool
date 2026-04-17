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

# 背景
st.markdown("<style>.main {background: linear-gradient(135deg, #FFF8E1, #FFFCF5) !important;}</style>", unsafe_allow_html=True)

# 初始化
if "messages" not in st.session_state:
    st.session_state.messages = []

# ==================== 安装引导（极简稳定版） ====================
st.subheader("📱 强烈推荐：添加到主屏幕使用")

st.markdown("""
**操作步骤：**

1. 点击浏览器右上角 **⋮** 菜单  
2. 选择 **“添加到主屏幕”** 或 **“安装应用”**  
3. 点击添加

**添加后：**
- 像原生 App 一样打开  
- 关闭时不再白屏  
- 使用更流畅稳定
""")

# 醒目静态按钮（只作为视觉提醒，不依赖点击反应）
st.markdown("""
<div style="text-align: center; margin: 15px 0;">
    <div style="background: #FF9800; color: white; padding: 16px 24px; border-radius: 50px; font-size: 17px; font-weight: bold;">
        📲 点击浏览器右上角 ⋮ → 添加到主屏幕
    </div>
</div>
""", unsafe_allow_html=True)

st.caption("添加成功后，主屏幕会出现 🥭 Mango AI 图标")

# ==================== 主界面 ====================
st.title("🥭 Mango AI")
st.caption("Zhipu + DeepSeek + Kimi + Doubao + Qwen\n低成本 · 高性能 · 连续对话")

col1, col2 = st.columns(2)
with col1:
    st.link_button("🚀 升级基础版 ($9.99/月)", 
                   "https://yufan-ai-chat.lemonsqueezy.com/checkout/buy/4e54840f-f7b5-4ccb-9051-f193b3a5ea87", 
                   use_container_width=True)
with col2:
    st.link_button("⭐ 升级高级版 ($14.99/月)", 
                   "https://yufan-ai-chat.lemonsqueezy.com/checkout/buy/18622988-9cb4-436f-a106-e3db06f8741a", 
                   use_container_width=True)

st.divider()

with st.sidebar:
    st.markdown("### 🥭 Mango AI")
    st.caption("多模型 AI 聊天工具")
    model_options = ["DeepSeek", "智谱 GLM-4", "Kimi", "豆包-Pro", "豆包-Lite", "通义千问"]
    st.radio("选择模型", model_options, label_visibility="collapsed")
    
    if st.button("🗑️ 清空聊天", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

for msg in st.session_state.messages:
    if msg["role"] == "user":
        st.chat_message("user").markdown(msg["content"])
    else:
        st.chat_message("assistant").markdown(msg["content"])

if prompt := st.chat_input("输入你的问题..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.session_state.messages.append({"role": "assistant", "content": "这是测试回复（实际接入 API 后会显示真实答案）"})
    st.rerun()

st.caption("Powered by Chinese Multi-Models · Deployed Overseas")
