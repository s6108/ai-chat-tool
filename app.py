import streamlit as st
import os
import base64
from openai import OpenAI
from supabase import create_client

st.set_page_config(page_title="Mango AI", page_icon="🥭", layout="centered")

# ====================== Supabase 配置 ======================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("Supabase 环境变量未配置，请检查 Render Environment Variables。")
    st.stop()

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ====================== API Keys ======================
def get_key(name: str):
    return os.getenv(name)

ZHIPU_API_KEY = get_key("ZHIPU_API_KEY")
DEEPSEEK_API_KEY = get_key("DEEPSEEK_API_KEY")
KIMI_API_KEY = get_key("KIMI_API_KEY")
DOUBAO_API_KEY = get_key("DOUBAO_API_KEY")
DASHSCOPE_API_KEY = get_key("DASHSCOPE_API_KEY")

# ====================== 模型配置 ======================
model_options = {
    "DeepSeek": {
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-chat",
        "key": DEEPSEEK_API_KEY,
    },
    "GLM-4V": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4/",
        "model": "glm-4v-plus",
        "key": ZHIPU_API_KEY,
    },
    "GLM-4": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4/",
        "model": "glm-4-plus",
        "key": ZHIPU_API_KEY,
    },
    "Kimi": {
        "base_url": "https://api.moonshot.cn/v1",
        "model": "moonshot-v1-8k",
        "key": KIMI_API_KEY,
    },
    "Doubao-Pro": {
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "model": "ep-20260415022601-jm5b7",
        "key": DOUBAO_API_KEY,
    },
    "Qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
        "key": DASHSCOPE_API_KEY,
    },
}

# ====================== 会话初始化 ======================
if "user" not in st.session_state:
    st.session_state.user = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "selected_model" not in st.session_state:
    st.session_state.selected_model = "DeepSeek"
if "auto_mode" not in st.session_state:
    st.session_state.auto_mode = True
if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0

# ====================== 未登录页面 ======================
if not st.session_state.user:
    st.title("🥭 Mango AI")
    st.subheader("请登录或注册才能继续使用")

    tab1, tab2 = st.tabs(["🔑 登录", "📝 注册"])

    with tab1:
        email = st.text_input("邮箱地址", key="login_email")
        password = st.text_input("密码", type="password", key="login_pass")

        if st.button("登录", use_container_width=True, key="login_btn"):
            try:
                res = supabase.auth.sign_in_with_password(
                    {"email": email, "password": password}
                )
                st.session_state.user = res.user
                st.success("登录成功！")
                st.rerun()
            except Exception as e:
                st.error(f"登录失败: {e}")

    with tab2:
        email_reg = st.text_input("注册邮箱", key="reg_email")
        password_reg = st.text_input("设置密码（至少6位）", type="password", key="reg_pass")

        if st.button("注册", use_container_width=True, key="reg_btn"):
            try:
                supabase.auth.sign_up(
                    {"email": email_reg, "password": password_reg}
                )
                st.success("注册成功！请查收邮箱验证邮件")
            except Exception as e:
                st.error(f"注册失败: {e}")

    st.stop()

# ====================== 已登录主界面 ======================
st.title("🥭 Mango AI")
st.write(f"欢迎回来，**{st.session_state.user.email}**")

# ====================== 侧边栏 ======================
with st.sidebar:
    if st.button("退出登录"):
        supabase.auth.sign_out()
        st.session_state.user = None
        st.session_state.messages = []
        st.rerun()

    st.link_button(
        "💎 升级高级会员 $7.99/月",
        "https://jjyo-ai-chat.lemonsqueezy.com/checkout/buy/ba6ddc8c-7c6f-40e1-b886-019ebc747a0a?lang=en",
    )

    st.markdown("### 模式选择")
    if st.button(
        "🔄 自动模式" if st.session_state.auto_mode else "🔧 手动模式",
        use_container_width=True,
    ):
        st.session_state.auto_mode = not st.session_state.auto_mode
        st.rerun()

    if not st.session_state.auto_mode:
        st.markdown("### 选择模型")
        for name in model_options.keys():
            label = "🔴 " + name if st.session_state.selected_model == name else "⚪ " + name
            if st.button(label, key=f"btn_{name}", use_container_width=True):
                st.session_state.selected_model = name
                st.rerun()

# ====================== 清空对话 ======================
if st.button("🗑️ 清空对话"):
    st.session_state.messages = []
    st.session_state.uploader_key += 1
    st.rerun()

# ====================== 显示聊天记录 ======================
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if isinstance(msg["content"], str):
            st.markdown(msg["content"])
        else:
            st.markdown("📸 图片已上传")

# ====================== 输入框和图片上传 ======================
uploaded_file = st.file_uploader(
    "上传图片",
    type=["png", "jpg", "jpeg"],
    key=f"upload_{st.session_state.uploader_key}",
)

prompt = st.chat_input("输入你的问题...")

# ====================== 处理输入 ======================
if prompt or uploaded_file is not None:
    user_content = prompt or ""

    if uploaded_file:
        b64 = base64.b64encode(uploaded_file.getvalue()).decode()
        user_content = [
            {"type": "text", "text": prompt or "请描述这张图片"},
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
            },
        ]

    st.session_state.messages.append(
        {"role": "user", "content": user_content}
    )

    with st.chat_message("user"):
        st.markdown(prompt if prompt else "📸 图片已上传")

    # 自动模式
    if st.session_state.auto_mode:
        if uploaded_file:
            st.session_state.selected_model = "GLM-4V"
        elif len(prompt or "") > 800:
            st.session_state.selected_model = "Kimi"
        elif len(prompt or "") > 300:
            st.session_state.selected_model = "Doubao-Pro"
        else:
            st.session_state.selected_model = "DeepSeek"

    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_response = ""

        try:
            cfg = model_options[st.session_state.selected_model]

            if not cfg["key"]:
                placeholder.error(
                    f"{st.session_state.selected_model} 的 API Key 未配置。"
                )
                st.stop()

            client = OpenAI(
                base_url=cfg["base_url"],
                api_key=cfg["key"],
            )

            # 图片模型保留图片消息；文字模型过滤图片消息
            if st.session_state.selected_model == "GLM-4V":
                api_messages = st.session_state.messages
            else:
                api_messages = [
                    m for m in st.session_state.messages
                    if isinstance(m["content"], str)
                ]

            stream = client.chat.completions.create(
                model=cfg["model"],
                messages=api_messages,
                stream=True,
                temperature=0.7,
                max_tokens=2000,
            )

            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    full_response += chunk.choices[0].delta.content
                    placeholder.markdown(full_response + "▌")

            placeholder.markdown(full_response)

            st.session_state.messages.append(
                {"role": "assistant", "content": full_response}
            )

            if uploaded_file:
                st.session_state.uploader_key += 1
                st.session_state.selected_model = "DeepSeek"
                st.rerun()

        except Exception as e:
            placeholder.error(f"调用失败: {str(e)}")

st.caption(
    f"当前模型: **{st.session_state.selected_model}** | 自动模式: {'✅' if st.session_state.auto_mode else '❌'}"
)
