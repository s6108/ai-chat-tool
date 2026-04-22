import streamlit as st
import os
from openai import OpenAI
import streamlit as st
import os
# ==================== PWA + iOS 图标配置 ====================
st.set_page_config(
    page_title="Mango AI",
    page_icon="🥭",
    layout="centered",
    initial_sidebar_state="expanded",
)

# 加强版 PWA 配置（专门针对 iOS Safari，解决默认 S 图标问题）
st.markdown("""
    <link rel="manifest" href="/manifest.json">
    <meta name="theme-color" content="#ff9800">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="default">
    
    <!-- iOS 专用苹果图标 - 这是解决 S 图标的关键 -->
    <link rel="apple-touch-icon" href="https://raw.githubusercontent.com/s6108/ai-chat-tool/main/微信图片_20260416184349_146_13.png">
    <link rel="apple-touch-icon" sizes="180x180" href="https://raw.githubusercontent.com/s6108/ai-chat-tool/main/微信图片_20260416184349_146_13.png">
    <link rel="apple-touch-icon" sizes="167x167" href="https://raw.githubusercontent.com/s6108/ai-chat-tool/main/微信图片_20260416184349_146_13.png">
    """, unsafe_allow_html=True)
# 安全读取 API Key
def get_key(name: str):
    return os.getenv(name) or st.secrets.get(name)

ZHIPU_API_KEY = get_key("ZHIPU_API_KEY")
DEEPSEEK_API_KEY = get_key("DEEPSEEK_API_KEY")
KIMI_API_KEY = get_key("KIMI_API_KEY")
DOUBAO_API_KEY = get_key("DOUBAO_API_KEY")
DASHSCOPE_API_KEY = get_key("DASHSCOPE_API_KEY")

# ====================== 界面 ======================
st.title("🥭 Mango AI")

st.markdown("""
**多模型 AI 聊天工具**  
Multi-Model AI Chat Tool · Low Cost · High Performance
""")

# 付费按钮
col1, col2 = st.columns(2)
with col1:
    st.link_button(
        "🚀 Upgrade Basic ($9.99/month)", 
        "https://yufan-ai-chat.lemonsqueezy.com/checkout/buy/4e54840f-f7b5-4ccb-9051-f193b3a5ea87?lang=en",
        use_container_width=True
    )
with col2:
    st.link_button(
        "⭐ Upgrade Premium ($14.99/month)", 
        "https://yufan-ai-chat.lemonsqueezy.com/checkout/buy/18622988-9cb4-436f-a106-e3db06f8741a?lang=en",
        use_container_width=True
    )

st.divider()

# 模型选择（默认 DeepSeek）
model_options = {
    "DeepSeek": ("https://api.deepseek.com", "deepseek-chat", DEEPSEEK_API_KEY),
    "智谱 GLM-4 / Zhipu GLM-4": ("https://open.bigmodel.cn/api/paas/v4/", "glm-4", ZHIPU_API_KEY),
    "Kimi": ("https://api.moonshot.cn/v1", "moonshot-v1-8k", KIMI_API_KEY),
    "豆包-Pro / Doubao-Pro": ("https://ark.cn-beijing.volces.com/api/v3", "ep-20260415022601-jm5b7", DOUBAO_API_KEY),
    "豆包-Lite / Doubao-Lite": ("https://ark.cn-beijing.volces.com/api/v3", "ep-20260415023354-lx4bm", DOUBAO_API_KEY),
    "通义千问 / Qwen": ("https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-plus", DASHSCOPE_API_KEY)
}

selected_model_name = st.sidebar.radio(
    "选择模型 / Select Model", 
    list(model_options.keys()), 
    index=0   # 默认选中第一个：DeepSeek
)

# ====================== 聊天逻辑 ======================
if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("输入你的问题... / Ask anything..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

          with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        
        try:
            # Streaming 调用（实时逐字显示）
            stream = client.chat.completions.create(
                model=model_name,
                messages=[{"role": m["role"], "content": m["content"]} for m in st.session_state.messages],
                stream=True,
                temperature=0.7,
                max_tokens=2000,
            )
            
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content is not None:
                    delta = chunk.choices[0].delta.content
                    full_response += delta
                    # 实时更新占位符，实现打字机效果
                    message_placeholder.markdown(full_response + "▌")
            
            # 最终显示完整回复（去掉光标）
            message_placeholder.markdown(full_response)
            
        except Exception as e:
            message_placeholder.error(f"调用失败: {str(e)}")
            full_response = "抱歉，模型调用出现错误，请稍后重试。"
        
    # 保存到聊天历史
    st.session_state.messages.append({"role": "assistant", "content": full_response})
            message_placeholder.markdown(full_response)
            
        except Exception as e:
            message_placeholder.error(f"调用失败: {str(e)}")
            full_response = "抱歉，模型调用出现错误，请稍后重试。"
        
    # 保存助手回复到聊天历史
    st.session_state.messages.append({"role": "assistant", "content": full_response})

st.caption("由中国主流大模型驱动 · 海外部署\nPowered by Chinese LLMs · Deployed Overseas")
