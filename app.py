import streamlit as st
import os
import base64
from openai import OpenAI

st.set_page_config(page_title="Mango AI", page_icon="🥭", layout="centered")

# ====================== 密钥 ======================
def get_key(name: str):
    return os.getenv(name) or st.secrets.get(name)

ZHIPU_API_KEY = get_key("ZHIPU_API_KEY")
DEEPSEEK_API_KEY = get_key("DEEPSEEK_API_KEY")
KIMI_API_KEY = get_key("KIMI_API_KEY")

model_options = {
    "DeepSeek": {"base_url": "https://api.deepseek.com", "model": "deepseek-chat", "key": DEEPSEEK_API_KEY},
    "GLM-4V":   {"base_url": "https://open.bigmodel.cn/api/paas/v4/", "model": "glm-4v-plus", "key": ZHIPU_API_KEY},
    "Kimi":     {"base_url": "https://api.moonshot.cn/v1", "model": "moonshot-v1-8k", "key": KIMI_API_KEY},
}

# ====================== 初始化 ======================
if "messages" not in st.session_state:
    st.session_state.messages = []
if "selected_model" not in st.session_state:
    st.session_state.selected_model = "DeepSeek"

# ====================== 侧边栏 ======================
with st.sidebar:
    st.title("🥭 Mango AI")
    st.markdown("### 模型选择")
    for name in model_options.keys():
        if st.button("🔴 " + name if st.session_state.selected_model == name else "⚪ " + name, 
                     key=f"btn_{name}", use_container_width=True):
            st.session_state.selected_model = name
            st.rerun()

# ====================== 主界面 ======================
st.title("🥭 Mango AI")

if st.button("🗑️ 清空对话"):
    st.session_state.messages = []
    st.rerun()

# 显示历史消息
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if isinstance(msg["content"], str):
            st.markdown(msg["content"])
        elif isinstance(msg["content"], list):
            for part in msg["content"]:
                if part.get("type") == "text":
                    st.markdown(part.get("text", ""))
                elif part.get("type") == "image_url":
                    st.image(part["image_url"]["url"])

# 输入
prompt = st.chat_input("输入你的问题...")
uploaded_file = st.file_uploader("📎 上传图片", type=["png", "jpg", "jpeg"])

# ====================== 处理 ======================
if prompt or uploaded_file:
    # 自动选择模型
    if uploaded_file:
        st.session_state.selected_model = "GLM-4V"
    elif len(prompt) > 800:
        st.session_state.selected_model = "Kimi"
    
    # 构建用户消息
    if uploaded_file:
        b64 = base64.b64encode(uploaded_file.getvalue()).decode()
        content = [
            {"type": "text", "text": prompt or "请描述这张图片"},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
        ]
        st.image(uploaded_file, caption="✅ 图片已上传")
    else:
        content = prompt

    st.session_state.messages.append({"role": "user", "content": content})

    with st.chat_message("user"):
        st.markdown(prompt or "已上传图片")

    # 调用AI
    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_response = ""
        try:
            cfg = model_options[st.session_state.selected_model]
            client = OpenAI(base_url=cfg["base_url"], api_key=cfg["key"])
            
            stream = client.chat.completions.create(
                model=cfg["model"],
                messages=st.session_state.messages,
                stream=True,
                temperature=0.7,
                max_tokens=2000
            )
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    full_response += chunk.choices[0].delta.content
                    placeholder.markdown(full_response + "▌")
            placeholder.markdown(full_response)
        except Exception as e:
            placeholder.error(f"错误: {str(e)}")
            full_response = "抱歉，调用失败，请重试。"

        st.session_state.messages.append({"role": "assistant", "content": full_response})

st.caption(f"当前模型: **{st.session_state.selected_model}**")
