import streamlit as st
import os
import base64
import requests
from openai import OpenAI

# ==================== 页面配置 ====================
st.set_page_config(page_title="Mango AI", page_icon="🥭", layout="centered")

st.markdown("""
    <link rel="manifest" href="/manifest.json">
    <meta name="theme-color" content="#ff9800">
""", unsafe_allow_html=True)

# ====================== 密钥 ======================
def get_key(name: str):
    return os.getenv(name) or st.secrets.get(name)

ZHIPU_API_KEY = get_key("ZHIPU_API_KEY")
DEEPSEEK_API_KEY = get_key("DEEPSEEK_API_KEY")
DOUBAO_API_KEY = get_key("DOUBAO_API_KEY")
DOUBAO_APPID = get_key("DOUBAO_APPID")
DOUBAO_TOKEN = get_key("DOUBAO_TOKEN")

# ====================== 模型 ======================
model_options = {
    "DeepSeek": {"base_url": "https://api.deepseek.com", "model": "deepseek-chat", "key": DEEPSEEK_API_KEY},
    "GLM-4V": {"base_url": "https://open.bigmodel.cn/api/paas/v4/", "model": "glm-4v-plus", "key": ZHIPU_API_KEY},
}

def auto_select_model(has_image=False):
    return "GLM-4V" if has_image else "DeepSeek"

# ====================== 豆包 ASR ======================
def doubao_asr(audio_bytes):
    if not DOUBAO_APPID or not DOUBAO_TOKEN:
        return "ASR未配置"
    try:
        url = "https://openspeech.bytedance.com/api/v2/asr"
        headers = {"Authorization": f"Bearer; {DOUBAO_TOKEN}"}
        config = {
            "app": {"appid": DOUBAO_APPID, "token": DOUBAO_TOKEN, "cluster": "volcengine"},
            "user": {"uid": "mango"},
            "request": {"reqid": "req1", "language": "zh", "input": {"format": "wav", "codec": "pcm"}}
        }
        files = {"file": ("audio.wav", audio_bytes, "audio/wav")}
        resp = requests.post(url, headers=headers, json=config, files=files, timeout=20)
        result = resp.json()
        if result.get("code") == 0:
            return result.get("result", {}).get("text", "无内容")
        return f"ASR失败: {result.get('message')}"
    except Exception as e:
        return f"ASR异常: {str(e)[:80]}"

# ====================== 初始化 ======================
if "messages" not in st.session_state:
    st.session_state.messages = []

# ====================== 界面 ======================
st.title("🥭 Mango AI")
st.markdown("**智能自动选择模型 · 支持语音和图像**")

if st.button("🗑️ 清空对话"):
    st.session_state.messages = []
    st.rerun()

# 显示历史消息
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        content = msg["content"]
        if isinstance(content, str):
            st.markdown(content)
        elif isinstance(content, list):
            for part in content:
                if part.get("type") == "text":
                    st.markdown(part.get("text", ""))
                elif part.get("type") == "image_url":
                    st.image(part["image_url"]["url"])

# ====================== 输入栏 ======================
col1, col2, col3 = st.columns([6, 1, 1])
with col1:
    prompt = st.chat_input("输入你的问题...")

with col2:
    uploaded_file = st.file_uploader("📎", type=["png","jpg","jpeg"], label_visibility="collapsed")

with col3:
    audio_value = st.audio_input("🎤", label_visibility="collapsed")

# ====================== 处理输入 ======================
if prompt or uploaded_file is not None or audio_value is not None:
    has_image = uploaded_file is not None
    selected_model = auto_select_model(has_image)
    
    user_content = []
    display_text = prompt or ""

    if uploaded_file:
        b64 = base64.b64encode(uploaded_file.getvalue()).decode()
        user_content.append({"type": "text", "text": display_text or "描述这张图片"})
        user_content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
        st.image(uploaded_file, caption="✅ 图片已上传")

    if audio_value:
        voice_text = doubao_asr(audio_value.getvalue())
        display_text += f"\n🎤 {voice_text}"
        user_content.append({"type": "text", "text": display_text})
        st.success(f"🎤 语音: {voice_text}")

    if prompt and not uploaded_file and not audio_value:
        user_content.append({"type": "text", "text": prompt})

    # 添加用户消息
    st.session_state.messages.append({"role": "user", "content": user_content if user_content else display_text})

    with st.chat_message("user"):
        st.markdown(display_text)

    # ====================== 调用AI ======================
    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_response = ""

        try:
            cfg = model_options[selected_model]
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
                    full_response += chunk.choices[0].delta.content
                    placeholder.markdown(full_response + "▌")
            
            placeholder.markdown(full_response)
            
        except Exception as e:
            placeholder.error(f"调用失败: {str(e)}")
            full_response = "抱歉，模型调用出现错误，请重试。"

        st.session_state.messages.append({"role": "assistant", "content": full_response})

st.caption(f"当前模型: **{selected_model}**（自动选择）")
