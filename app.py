import streamlit as st
import os
from openai import OpenAI

# ==================== PWA + iOS 图标配置 ====================
st.set_page_config(
    page_title="Mango AI",
    page_icon="🥭",
    layout="centered",
    initial_sidebar_state="expanded",
)

# PWA 配置
st.markdown("""
    <link rel="manifest" href="/manifest.json">
    <meta name="theme-color" content="#ff9800">
    """, unsafe_allow_html=True)

# ====================== 安全读取 API Key ======================
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
**Multi-Model AI Chat Tool**  
Low Cost · High Performance
""")

# 付费按钮
col1, col2 = st.columns(2)
with col1:
    st.link_button("🚀 Basic $9.99", 
                   "https://yufan-ai-chat.lemonsqueezy.com/checkout/buy/4e54840f-f7b5-4ccb-9051-f193b3a5ea87?lang=en", 
                   use_container_width=True)
with col2:
    st.link_button("⭐ Premium $14.99", 
                   "https://yufan-ai-chat.lemonsqueezy.com/checkout/buy/18622988-9cb4-436f-a106-e3db06f8741a?lang=en", 
                   use_container_width=True)

st.divider()

# ====================== 模型选择（红点按钮） ======================
st.subheader("Select Model")

model_options = {
    "DeepSeek": ("https://api.deepseek.com", "deepseek-chat", DEEPSEEK_API_KEY),
    "GLM-4": ("https://open.bigmodel.cn/api/paas/v4/", "glm-4", ZHIPU_API_KEY),
    "Kimi": ("https://api.moonshot.cn/v1", "moonshot-v1-8k", KIMI_API_KEY),
    "Doubao-Pro": ("https://ark.cn-beijing.volces.com/api/v3", "ep-20260415022601-jm5b7", DOUBAO_API_KEY),
    "Doubao-Lite": ("https://ark.cn-beijing.volces.com/api/v3", "ep-20260415023354-lx4bm", DOUBAO_API_KEY),
    "Qwen": ("https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-plus", DASHSCOPE_API_KEY)
}

# 当前选中模型
if "selected_model_name" not in st.session_state:
    st.session_state.selected_model_name = "DeepSeek"

# 横向小红点按钮
cols = st.columns(len(model_options))
for idx, (name, (url, mdl, key)) in enumerate(model_options.items()):
    with cols[idx]:
        # 选中状态显示红色实心点，未选中显示空心点
        is_selected = st.session_state.selected_model_name == name
        button_label = "🔴 " + name if is_selected else "⚪ " + name
        
        if st.button(button_label, use_container_width=True, key=f"model_{idx}"):
            st.session_state.selected_model_name = name
            st.session_state.base_url = url
            st.session_state.model_name = mdl
            st.session_state.api_key = key
            st.rerun()

st.caption(f"Current Model: **{st.session_state.selected_model_name}**")

st.divider()

# ====================== 聊天逻辑 ======================
if "messages" not in st.session_state:
    st.session_state.messages = []

if st.button("🗑️ Clear Chat"):
    st.session_state.messages = []
    st.rerun()

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# ====================== 输入区域（带附件和语音） ======================
col_input, col_attach, col_voice = st.columns([6, 1, 1])

with col_input:
    prompt = st.chat_input("Ask anything...")

with col_attach:
    uploaded_file = st.file_uploader("📎", type=["png", "jpg", "jpeg"], 
                                     label_visibility="collapsed", key="file_uploader")

with col_voice:
    audio_value = st.audio_input("🎤", label_visibility="collapsed", key="voice_input")

# 处理图片上传
if uploaded_file is not None:
    st.image(uploaded_file, width=300)
    st.success(f"✅ 图片已上传: {uploaded_file.name}")
    # 这里可以后续让 AI 分析图片（需使用视觉模型）

# 处理语音输入
if audio_value is not None:
    st.audio(audio_value)
    st.success("✅ 语音已录制")
    # 这里可以后续调用语音转文字功能

# ====================== 发送消息 ======================
if prompt or uploaded_file is not None or audio_value is not None:
    user_content = prompt if prompt else ""
    
    if uploaded_file is not None:
        user_content += f"\n[图片: {uploaded_file.name}]"
    
    if audio_value is not None:
        user_content += "\n[语音消息已录制]"

    if user_content:
        st.session_state.messages.append({"role": "user", "content": user_content})
        with st.chat_message("user"):
            st.markdown(user_content)
            if uploaded_file is not None:
                st.image(uploaded_file, width=300)

        # AI 回复
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""
            
            try:
                client = OpenAI(base_url=st.session_state.base_url, api_key=st.session_state.api_key)
                
                stream = client.chat.completions.create(
                    model=st.session_state.model_name,
                    messages=[{"role": m["role"], "content": m["content"]} for m in st.session_state.messages],
                    stream=True,
                    temperature=0.7,
                    max_tokens=2000,
                )
                
                for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content is not None:
                        full_response += chunk.choices[0].delta.content
                        message_placeholder.markdown(full_response + "▌")
                
                message_placeholder.markdown(full_response)
                
            except Exception as e:
                message_placeholder.error(f"调用失败: {str(e)}")
                full_response = "抱歉，模型调用出现错误，请稍后重试。"
            
        st.session_state.messages.append({"role": "assistant", "content": full_response})
        st.caption("由中国主流大模型驱动 · 海外部署\nPowered by Chinese LLMs · Deployed Overseas")
