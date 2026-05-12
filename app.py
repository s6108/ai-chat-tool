import streamlit as st
import os
import base64
import requests
from openai import OpenAI

# ==================== PWA + iOS 配置 ====================
st.set_page_config(
    page_title="Mango AI",
    page_icon="🥭",
    layout="centered",
    initial_sidebar_state="expanded",
)

st.markdown("""
    <link rel="manifest" href="/manifest.json">
    <meta name="theme-color" content="#ff9800">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="default">
    <link rel="apple-touch-icon" href="https://raw.githubusercontent.com/s6108/ai-chat-tool/main/微信图片_20260416184349_146_13.png">
""", unsafe_allow_html=True)

# ====================== 安全读取密钥 ======================
def get_key(name: str):
    return os.getenv(name) or st.secrets.get(name)

# API Keys
ZHIPU_API_KEY = get_key("ZHIPU_API_KEY")
DEEPSEEK_API_KEY = get_key("DEEPSEEK_API_KEY")
KIMI_API_KEY = get_key("KIMI_API_KEY")
DOUBAO_API_KEY = get_key("DOUBAO_API_KEY")
DASHSCOPE_API_KEY = get_key("DASHSCOPE_API_KEY")
DOUBAO_APPID = get_key("DOUBAO_APPID")
DOUBAO_TOKEN = get_key("DOUBAO_TOKEN")

# ====================== 模型配置 ======================
model_options = {
    "DeepSeek": {"base_url": "https://api.deepseek.com", "model": "deepseek-chat", "key": DEEPSEEK_API_KEY},
    "GLM-4V": {"base_url": "https://open.bigmodel.cn/api/paas/v4/", "model": "glm-4v-plus", "key": ZHIPU_API_KEY},
    "GLM-4": {"base_url": "https://open.bigmodel.cn/api/paas/v4/", "model": "glm-4-plus", "key": ZHIPU_API_KEY},
    "Kimi": {"base_url": "https://api.moonshot.cn/v1", "model": "moonshot-v1-8k", "key": KIMI_API_KEY},
    "Doubao-Pro": {"base_url": "https://ark.cn-beijing.volces.com/api/v3", "model": "ep-20260415022601-jm5b7", "key": DOUBAO_API_KEY},
    "Qwen": {"base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen-plus", "key": DASHSCOPE_API_KEY},
}

# ====================== 豆包 ASR 语音转文字 ======================
def doubao_asr(audio_bytes):
    if not DOUBAO_APPID or not DOUBAO_TOKEN:
        return "❌ 豆包语音识别未配置"
    
    url = "https://openspeech.bytedance.com/api/v2/asr"
    headers = {"Authorization": f"Bearer; {DOUBAO_TOKEN}"}
    
    payload = {
        "app": {"appid": DOUBAO_APPID, "token": DOUBAO_TOKEN, "cluster": "volcengine"},
        "user": {"uid": "mango_ai_user"},
        "request": {"reqid": "mango_asr_req", "language": "zh", "input": {"format": "wav", "codec": "pcm"}},
    }
    
    files = {"file": ("audio.wav", audio_bytes, "audio/wav")}
    
    try:
        resp = requests.post(url, headers=headers, data={"config": str(payload)}, files=files, timeout=15)
        result = resp.json()
        if result.get("code") == 0:
            return result["result"]["text"]
        else:
            return f"识别失败: {result.get('message')}"
    except Exception as e:
        return f"ASR 错误: {str(e)}"

# ====================== 初始化 ======================
if "messages" not in st.session_state:
    st.session_state.messages = []
if "selected_model" not in st.session_state:
    st.session_state.selected_model = "GLM-4V"

# ====================== 界面 ======================
st.title("🥭 Mango AI")

st.markdown("**多模型 AI 聊天 · 支持语音 + 图像**")

# 模型选择（红点按钮）
cols = st.columns(len(model_options))
for i, (name, info) in enumerate(model_options.items()):
    with cols[i]:
        if st.button(
            "🔴" if st.session_state.selected_model == name else "⚪",
            key=f"model_{name}",
            help=name
        ):
            st.session_state.selected_model = name
            st.rerun()

st.caption(f"当前模型: **{st.session_state.selected_model}**")

# 清空对话
if st.button("🗑️ 清空对话"):
    st.session_state.messages = []
    st.rerun()

# ====================== 聊天记录 ======================
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if isinstance(msg["content"], str):
            st.markdown(msg["content"])
        elif isinstance(msg["content"], list):
            for part in msg["content"]:
                if part["type"] == "text":
                    st.markdown(part["text"])
                elif part["type"] == "image_url":
                    st.image(part["image_url"]["url"])

# ====================== 输入区域 ======================
col_input, col_file, col_voice = st.columns([6, 1, 1])

with col_input:
    prompt = st.chat_input("输入问题 / Ask anything...")

with col_file:
    uploaded_file = st.file_uploader("📎", type=["png", "jpg", "jpeg"], label_visibility="collapsed")

with col_voice:
    audio_value = st.audio_input("🎤", label_visibility="collapsed")

# ====================== 处理输入 ======================
user_content = []

if prompt:
    user_content.append({"type": "text", "text": prompt})

if uploaded_file:
    bytes_data = uploaded_file.getvalue()
    b64 = base64.b64encode(bytes_data).decode()
    user_content.append({
        "type": "image_url",
        "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
    })
    st.image(uploaded_file, caption="已上传图片")

if audio_value:
    text = doubao_asr(audio_value.getvalue())
    if text:
        prompt = (prompt or "") + "\n[语音内容] " + text
        user_content.append({"type": "text", "text": f"🎤 {text}"})
        st.success(f"语音识别: {text}")

if user_content:
    full_prompt = prompt or "描述这张图片"
    st.session_state.messages.append({"role": "user", "content": user_content})
    
    with st.chat_message("user"):
        st.markdown(full_prompt if isinstance(full_prompt, str) else "已发送图片/语音")

    # 调用模型
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        
        try:
            cfg = model_options[st.session_state.selected_model]
            client = OpenAI(base_url=cfg["base_url"], api_key=cfg["key"])
            
            stream = client.chat.completions.create(
                model=cfg["model"],
                messages=[{"role": m["role"], "content": m["content"]} for m in st.session_state.messages],
                stream=True,
                temperature=0.7,
                max_tokens=2000,
            )
            
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    delta = chunk.choices[0].delta.content
                    full_response += delta
                    message_placeholder.markdown(full_response + "▌")
            
            message_placeholder.markdown(full_response)
            
        except Exception as e:
            message_placeholder.error(f"调用失败: {str(e)}")
            full_response = "抱歉，模型调用出现错误。"
        
        st.session_state.messages.append({"role": "assistant", "content": full_response})

st.caption("由中国主流大模型驱动 · 支持语音识别与图像理解\nPowered by Chinese LLMs + Doubao ASR")
