import streamlit as st
import os
import base64
import requests
import json
from openai import OpenAI

# ==================== PWA 配置 ====================
st.set_page_config(page_title="Mango AI", page_icon="🥭", layout="centered")

st.markdown("""
    <link rel="manifest" href="/manifest.json">
    <meta name="theme-color" content="#ff9800">
    <meta name="apple-mobile-web-app-capable" content="yes">
""", unsafe_allow_html=True)

# ====================== 读取密钥 ======================
def get_key(name: str):
    return os.getenv(name) or st.secrets.get(name)

ZHIPU_API_KEY = get_key("ZHIPU_API_KEY")
DEEPSEEK_API_KEY = get_key("DEEPSEEK_API_KEY")
DOUBAO_API_KEY = get_key("DOUBAO_API_KEY")
DOUBAO_APPID = get_key("DOUBAO_APPID")
DOUBAO_TOKEN = get_key("DOUBAO_TOKEN")

# ====================== 模型配置 ======================
model_options = {
    "DeepSeek": {"base_url": "https://api.deepseek.com", "model": "deepseek-chat", "key": DEEPSEEK_API_KEY},
    "Doubao-Pro": {"base_url": "https://ark.cn-beijing.volces.com/api/v3", "model": "ep-20260415022601-jm5b7", "key": DOUBAO_API_KEY},
    "GLM-4V": {"base_url": "https://open.bigmodel.cn/api/paas/v4/", "model": "glm-4v-plus", "key": ZHIPU_API_KEY},
}

# ====================== 自动选择模型 ======================
def auto_select_model(has_image=False):
    if has_image:
        return "GLM-4V"
    return "DeepSeek"   # 最性价比

# ====================== 豆包 ASR（已优化，解决500错误） ======================
def doubao_asr(audio_bytes):
    if not DOUBAO_APPID or not DOUBAO_TOKEN:
        return "❌ 未配置豆包ASR密钥"
    
    url = "https://openspeech.bytedance.com/api/v2/asr"
    headers = {"Authorization": f"Bearer; {DOUBAO_TOKEN}"}
    
    config = {
        "app": {
            "appid": DOUBAO_APPID,
            "token": DOUBAO_TOKEN,
            "cluster": "volcengine"
        },
        "user": {"uid": "mango_user"},
        "request": {
            "reqid": "req_" + str(int(os.times()[4] * 1000)),
            "language": "zh",
            "input": {"format": "wav", "codec": "pcm"}
        }
    }
    
    try:
        files = {"file": ("audio.wav", audio_bytes, "audio/wav")}
        # 使用 json= 参数发送（关键修复）
        response = requests.post(url, headers=headers, json=config, files=files, timeout=25)
        
        if response.status_code != 200:
            return f"ASR失败 HTTP{response.status_code}"
        
        result = response.json()
        if result.get("code") == 0:
            text = result.get("result", {}).get("text", "")
            return text if text else "（无识别结果）"
        else:
            return f"识别失败: {result.get('message')}"
    except Exception as e:
        return f"ASR异常: {str(e)[:100]}"

# ====================== 初始化 ======================
if "messages" not in st.session_state:
    st.session_state.messages = []

# ====================== 界面 ======================
st.title("🥭 Mango AI")
st.markdown("**智能自动选择 · 语音 + 图像**")

if st.button("🗑️ 清空对话"):
    st.session_state.messages = []
    st.rerun()

# 显示聊天记录
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if isinstance(msg.get("content"), str):
            st.markdown(msg["content"])
        elif isinstance(msg.get("content"), list):
            for part in msg["content"]:
                if part.get("type") == "text":
                    st.markdown(part.get("text", ""))
                elif part.get("type") == "image_url":
                    st.image(part["image_url"]["url"])

# 输入区域
col_input, col_file, col_voice = st.columns([6, 1, 1])

with col_input:
    prompt = st.chat_input("输入问题... / Ask anything...")

with col_file:
    uploaded_file = st.file_uploader("📎", type=["png", "jpg", "jpeg"], label_visibility="collapsed")

with col_voice:
    audio_value = st.audio_input("🎤", label_visibility="collapsed")

# ====================== 处理并发送 ======================
if prompt or uploaded_file or audio_value:
    has_image = bool(uploaded_file)
    selected_model = auto_select_model(has_image)
    
    user_content = []
    display_text = prompt or ""
    
    if uploaded_file:
        b64 = base64.b64encode(uploaded_file.getvalue()).decode()
        user_content.append({"type": "text", "text": display_text or "请描述这张图片"})
        user_content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
        st.image(uploaded_file, caption="✅ 图片已上传")
    
    if audio_value:
        voice_text = doubao_asr(audio_value.getvalue())
        display_text = (display_text or "") + f"\n🎤 {voice_text}"
