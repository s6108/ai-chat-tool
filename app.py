import streamlit as st
import os
import base64
import requests
from openai import OpenAI

st.set_page_config(page_title="Mango AI", page_icon="🥭", layout="centered")

st.markdown("""<meta name="theme-color" content="#ff9800">""", unsafe_allow_html=True)

# ====================== 密钥 ======================
def get_key(name: str):
    return os.getenv(name) or st.secrets.get(name)

ZHIPU_API_KEY = get_key("ZHIPU_API_KEY")
DEEPSEEK_API_KEY = get_key("DEEPSEEK_API_KEY")
DOUBAO_APPID = get_key("DOUBAO_APPID")
DOUBAO_TOKEN = get_key("DOUBAO_TOKEN")

model_options = {
    "DeepSeek": {"base_url": "https://api.deepseek.com", "model": "deepseek-chat", "key": DEEPSEEK_API_KEY},
    "GLM-4V": {"base_url": "https://open.bigmodel.cn/api/paas/v4/", "model": "glm-4v-plus", "key": ZHIPU_API_KEY},
}

def auto_select_model(has_image=False):
    return "GLM-4V" if has_image else "DeepSeek"

# ====================== 简化版豆包 ASR ======================
def doubao_asr(audio_bytes):
    if not DOUBAO_APPID or not DOUBAO_TOKEN:
        return "ASR 未配置"
    
    url = "https://openspeech.bytedance.com/api/v2/asr"
    headers = {"Authorization": f"Bearer; {DOUBAO_TOKEN}"}
    
    config = {
        "app": {"appid": DOUBAO_APPID, "token": DOUBAO_TOKEN, "cluster": "volcengine"},
        "user": {"uid": "mango"},
        "request": {"reqid": "req1", "language": "zh", "input": {"format": "pcm", "codec": "raw"}}
    }
    
    try:
        files = {"file": ("audio.pcm", audio_bytes, "audio/pcm")}
        resp = requests.post(url, headers=headers, json=config, files=files, timeout=20)
        
        st.write(f"ASR 状态码: **{resp.status_code}**")   # 调试
        
        if resp.status_code == 200:
            try:
                result = resp.json()
                if result.get("code") == 0:
                    text = result.get("result", {}).get("text", "")
                    return text if text else "（无识别内容）"
                return f"服务错误: {result.get('message')}"
            except:
                return f"返回内容: {resp.text[:150]}"
        else:
            return f"HTTP {resp.status_code} 错误"
    except Exception as e:
        return f"异常: {str(e)}"

# ====================== 主界面 ======================
if "messages" not in st.session_state:
    st.session_state.messages = []
if "current_model" not in st.session_state:
    st.session_state.current_model = "DeepSeek"

st.title("🥭 Mango AI")
st.markdown("**智能聊天 · 支持语音和图片**")

if st.button("🗑️ 清空对话"):
    st.session_state.messages = []
    st.rerun()

# 显示消息
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if isinstance(msg["content"], str):
            st.markdown(msg["content"])
        elif isinstance(msg["content"], list):
            for p in msg["content"]:
                if p.get("type") == "text":
                    st.markdown(p.get("text", ""))
                elif p.get("type") == "image_url":
                    st.image(p["image_url"]["url"])

# 输入
c1, c2, c3 = st.columns([6,1,1])
with c1:
    prompt = st.chat_input("输入你的问题...")
with c2:
    uploaded_file = st.file_uploader("📎", type=["png","jpg","jpeg"], label_visibility="collapsed")
with c3:
    audio_value = st.audio_input("🎤", label_visibility="collapsed")

# 处理
if prompt or uploaded_file or audio_value:
    has_image = bool(uploaded_file)
    st.session_state.current_model = auto_select_model(has_image)
    
    user_content = []
    display_text = prompt or ""

    if uploaded_file:
        b64 = base64.b64encode(uploaded_file.getvalue()).decode()
        user_content.append({"type": "text", "text": display_text or "描述图片"})
        user_content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
        st.image(uploaded_file)

    if audio_value:
        voice_text = doubao_asr(audio_value.getvalue())
        display_text += f"\n🎤 {voice_text}"
        user_content.append({"type": "text", "text": display_text})
        st.success(f"语音识别: {voice_text}")

    if prompt and not uploaded_file and not audio_value:
        user_content.append({"type": "text", "text": prompt})

    st.session_state.messages.append({"role": "user", "content": user_content or display_text})

    with st.chat_message("user"):
        st.markdown(display_text)

    # AI回复
    with st.chat_message("assistant"):
        placeholder = st.empty()
        full = ""
        try:
            cfg = model_options[st.session_state.current_model]
            client = OpenAI(base_url=cfg["base_url"], api_key=cfg["key"])
            stream = client.chat.completions.create(
                model=cfg["model"],
                messages=[{"role": m["role"], "content": m["content"]} for m in st.session_state.messages],
                stream=True, temperature=0.7
            )
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    full += chunk.choices[0].delta.content
                    placeholder.markdown(full + "▌")
            placeholder.markdown(full)
        except Exception as e:
            placeholder.error(f"错误: {str(e)}")
            full = "抱歉，出错了"

        st.session_state.messages.append({"role": "assistant", "content": full})

st.caption(f"当前模型: **{st.session_state.current_model}**")
