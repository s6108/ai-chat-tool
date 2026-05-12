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

ZHIPU_API_KEY = get_key("ZHIPU_API_KEY")
DEEPSEEK_API_KEY = get_key("DEEPSEEK_API_KEY")
KIMI_API_KEY = get_key("KIMI_API_KEY")
DOUBAO_API_KEY = get_key("DOUBAO_API_KEY")
DASHSCOPE_API_KEY = get_key("DASHSCOPE_API_KEY")
DOUBAO_APPID = get_key("DOUBAO_APPID")
DOUBAO_TOKEN = get_key("DOUBAO_TOKEN")

# ====================== 模型配置（性价比优先） ======================
model_options = {
    "DeepSeek": {"base_url": "https://api.deepseek.com", "model": "deepseek-chat", "key": DEEPSEEK_API_KEY, "priority": 1},
    "Doubao-Pro": {"base_url": "https://ark.cn-beijing.volces.com/api/v3", "model": "ep-20260415022601-jm5b7", "key": DOUBAO_API_KEY, "priority": 2},
    "GLM-4V": {"base_url": "https://open.bigmodel.cn/api/paas/v4/", "model": "glm-4v-plus", "key": ZHIPU_API_KEY, "priority": 3},
    "GLM-4": {"base_url": "https://open.bigmodel.cn/api/paas/v4/", "model": "glm-4-plus", "key": ZHIPU_API_KEY, "priority": 4},
    "Qwen": {"base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen-plus", "key": DASHSCOPE_API_KEY, "priority": 5},
}

# ====================== 自动选择最具性价比模型 ======================
def auto_select_model(has_image=False, has_voice=False):
    if has_image:
        return "GLM-4V"          # 图像识别最强
    if has_voice:
        return "DeepSeek"        # 语音后处理最快最稳
    return "DeepSeek"            # 默认最便宜最快

# ====================== 豆包 ASR 语音转文字（最终稳定版） ======================
def doubao_asr(audio_bytes):
    if not DOUBAO_APPID or not DOUBAO_TOKEN:
        return "❌ 豆包语音识别未配置"
    
    url = "https://openspeech.bytedance.com/api/v2/asr"
    headers = {"Authorization": f"Bearer; {DOUBAO_TOKEN}"}
    
    config = {
        "app": {"appid": DOUBAO_APPID, "token": DOUBAO_TOKEN, "cluster": "volcengine"},
        "user": {"uid": "mango_ai_user"},
        "request": {
            "reqid": f"mango_{int(os.times()[4]*1000)}",
            "language": "zh",
            "input": {"format": "wav", "codec": "pcm"}
        }
    }
    
    try:
        files = {"file": ("audio.wav", audio_bytes, "audio/wav")}
        resp = requests.post(url, headers=headers, data={"config": str(config)}, files=files, timeout=20)
        
        if resp.status_code != 200:
            return f"ASR 请求失败 HTTP{resp.status_code}"
        
        result = resp.json()
        if result.get("code") == 0 and result.get("result", {}).get("text"):
            return result["result"]["text"]
        else:
            return f"识别失败: {result.get('message', str(result))}"
    except Exception as e:
        return f"ASR 错误: {str(e)}"

# ====================== 初始化 ======================
if "messages" not in st.session_state:
    st.session_state.messages = []
if "current_model" not in st.session_state:
    st.session_state.current_model = "DeepSeek"

# ====================== 界面 ======================
st.title("🥭 Mango AI")
st.markdown("**智能多模型 · 自动选择性价比最高**")

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
                if part.get("type") == "text":
                    st.markdown(part["text"])
                elif part.get("type") == "image_url":
                    st.image(part["image_url"]["url"])

# ====================== 输入区域（语音 + 图片） ======================
col_input, col_file, col_voice = st.columns([6, 1, 1])

with col_input:
    prompt = st.chat_input("输入你的问题... / Ask anything...")

with col_file:
    uploaded_file = st.file_uploader("📎", type=["png", "jpg", "jpeg"], label_visibility="collapsed")

with col_voice:
    audio_value = st.audio_input("🎤", label_visibility="collapsed")

# ====================== 处理输入 ======================
user_content = []
has_image = False
has_voice = False
final_prompt = prompt or ""

if uploaded_file:
    bytes_data = uploaded_file.getvalue()
    b64 = base64.b64encode(bytes_data).decode()
    user_content.append({"type": "text", "text": final_prompt or "请描述这张图片"})
    user_content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
    has_image = True
    st.image(uploaded_file, caption="✅ 图片已上传")

if audio_value:
    voice_text = doubao_asr(audio_value.getvalue())
    final_prompt = (final_prompt or "") + f"\n[语音] {voice_text}"
    user_content.append({"type": "text", "text": final_prompt})
    has_voice = True
    st.success(f"🎤 语音识别成功: {voice_text}")

if prompt and not uploaded_file and not audio_value:
    user_content.append({"type": "text", "text": prompt})

# ====================== 发送消息 ======================
if user_content:
    st.session_state.current_model = auto_select_model(has_image, has_voice)
    
    st.session_state.messages.append({"role": "user", "content": user_content})
    
    with st.chat_message("user"):
        st.markdown(final_prompt)

    # 调用模型
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        
        try:
            cfg = model_options[st.session_state.current_model]
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
            full_response = "抱歉，模型调用出现错误，请稍后重试。"
        
        st.session_state.messages.append({"role": "assistant", "content": full_response})

st.caption(f"当前模型: **{st.session_state.current_model}**（自动选择）\n"
           "由中国主流大模型驱动 · 支持语音识别与图像理解\n"
           "Powered by Chinese LLMs + Doubao ASR")
