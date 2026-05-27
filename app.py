import streamlit as st
import os
import base64
from openai import OpenAI
from supabase import create_client, Client

st.set_page_config(page_title="Mango AI", page_icon="🥭", layout="centered")

# ====================== Supabase 配置 ======================
SUPABASE_URL = "https://oeiomraxpgmirnubtrug.supabase.co"
SUPABASE_KEY = "sb_publishable_oQ6lNrM38kY1F_xWnzQI6w_LK86YMpi"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ====================== API Keys ======================
def get_key(name: str):
    return os.getenv(name) or st.secrets.get(name)

ZHIPU_API_KEY = get_key("ZHIPU_API_KEY")
DEEPSEEK_API_KEY = get_key("DEEPSEEK_API_KEY")
KIMI_API_KEY = get_key("KIMI_API_KEY")
DOUBAO_API_KEY = get_key("DOUBAO_API_KEY")
DASHSCOPE_API_KEY = get_key("DASHSCOPE_API_KEY")

# ====================== 模型配置 ======================
model_options = {
    "DeepSeek":  {"base_url": "https://api.deepseek.com", "model": "deepseek-chat", "key": DEEPSEEK_API_KEY},
    "GLM-4V":    {"base_url": "https://open.bigmodel.cn/api/paas/v4/", "model": "glm-4v-plus", "key": ZHIPU_API_KEY},
    "GLM-4":     {"base_url": "https://open.bigmodel.cn/api/paas/v4/", "model": "glm-4-plus", "key": ZHIPU_API_KEY},
    "Kimi":      {"base_url": "https://api.moonshot.cn/v1", "model": "moonshot-v1-8k", "key": KIMI_API_KEY},
    "Doubao-Pro":{"base_url": "https://ark.cn-beijing.volces.com/api/v3", "model": "ep-20260415022601-jm5b7", "key": DOUBAO_API_KEY},
    "Qwen":      {"base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen-plus", "key": DASHSCOPE_API_KEY},
}

# ====================== 固定底部输入框（加强版） ======================
st.markdown("""
    <style>
        .bottom-bar {
            position: fixed !important;
            bottom: 0 !important;
            left: 0 !important;
            right: 0 !important;
            background: white;
            padding: 12px 15px 30px 15px;
            box-shadow: 0 -4px 30px rgba(0,0,0,0.25);
            z-index: 10000;
            border-top: 1px solid #ddd;
        }
        .main .block-container {
            padding-bottom: 260px !important;
        }
    </style>
""", unsafe_allow_html=True)

# ====================== 会话初始化 ======================
if "user" not in st.session_state:
    st.session_state.user = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "selected_model" not in st.session_state:
    st.session_state.selected_model = "DeepSeek"
if "auto_mode" not in st.session_state:
    st.session_state.auto_mode = True
if "guest_count" not in st.session_state:
    st.session_state.guest_count = 0

DAILY_GUEST_LIMIT = 20

# ====================== 未登录 - 游客模式 ======================
if not st.session_state.user:
    st.title("🥭 Mango AI")
    st.info(f"🔓 游客模式（今日已用 {st.session_state.guest_count}/{DAILY_GUEST_LIMIT} 条）")
    
    if st.button("登录 / 注册", use_container_width=True):
        st.session_state.show_login = True

    if st.session_state.get("show_login", False):
        with st.expander("登录 / 注册", expanded=True):
            tab1, tab2 = st.tabs(["登录", "注册"])
            with tab1:
                email = st.text_input("邮箱地址", key="login_email")
                password = st.text_input("密码", type="password", key="login_pass")
                if st.button("登录", use_container_width=True, key="login_btn"):
                    try:
                        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                        st.session_state.user = res.user
                        st.success("登录成功！")
                        st.rerun()
                    except Exception as e:
                        st.error(f"登录失败: {e}")
            with tab2:
                email_reg = st.text_input("注册邮箱", key="reg_email")
                password_reg = st.text_input("设置密码", type="password", key="reg_pass")
                if st.button("注册", use_container_width=True, key="reg_btn"):
                    try:
                        res = supabase.auth.sign_up({"email": email_reg, "password": password_reg})
                        st.success("注册成功！请查收邮箱验证")
                    except Exception as e:
                        st.error(f"注册失败: {e}")

# ====================== 已登录主界面 ======================
if st.session_state.user:
    st.title("🥭 Mango AI")
    st.write(f"欢迎回来，**{st.session_state.user.email}**")

# 侧边栏
with st.sidebar:
    if st.session_state.user and st.button("退出登录"):
        supabase.auth.sign_out()
        st.session_state.user = None
        st.rerun()

    st.link_button("💎 升级高级会员 $7.99/月", 
                   "https://jjyo-ai-chat.lemonsqueezy.com/checkout/buy/ba6ddc8c-7c6f-40e1-b886-019ebc747a0a?lang=en")

    st.markdown("### 模式选择")
    if st.button("🔄 自动模式" if st.session_state.auto_mode else "🔧 手动模式", use_container_width=True):
        st.session_state.auto_mode = not st.session_state.auto_mode
        st.rerun()

    if not st.session_state.auto_mode:
        st.markdown("### 选择模型")
        for name in model_options.keys():
            label = "🔴 " + name if st.session_state.selected_model == name else "⚪ " + name
            if st.button(label, key=f"btn_{name}", use_container_width=True):
                st.session_state.selected_model = name
                st.rerun()

if st.button("🗑️ 清空对话"):
    st.session_state.messages = []
    st.rerun()

# 显示聊天记录
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if isinstance(msg["content"], list):
            for part in msg["content"]:
                if part.get("type") == "text":
                    st.markdown(part.get("text"))
                elif part.get("type") == "image_url":
                    st.image(part["image_url"]["url"], use_column_width=True)
        else:
            st.markdown(msg["content"])

# ====================== 固定底部输入 ======================
st.markdown('<div class="bottom-bar">', unsafe_allow_html=True)
col1, col2 = st.columns([7, 1])
with col1:
    prompt = st.chat_input("输入你的问题...")
with col2:
    uploaded_file = st.file_uploader("📎", type=["png","jpg","jpeg"], label_visibility="collapsed")
st.markdown('</div>', unsafe_allow_html=True)

# ====================== 处理输入 ======================
if prompt or uploaded_file is not None:
    if not st.session_state.user:
        if st.session_state.guest_count >= DAILY_GUEST_LIMIT:
            st.error("游客每日限额已用完，请登录")
            st.stop()
        st.session_state.guest_count += 1

    # 只为当前问题处理图片
    user_content = prompt
    if uploaded_file:
        b64 = base64.b64encode(uploaded_file.getvalue()).decode()
        user_content = [
            {"type": "text", "text": prompt or "请描述这张图片"},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
        ]
        st.image(uploaded_file, caption="✅ 图片已上传")

    st.session_state.messages.append({"role": "user", "content": user_content})

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

    # 调用模型
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
                if chunk.choices and chunk.choices[0].delta.content:
                    full_response += chunk.choices[0].delta.content
                    placeholder.markdown(full_response + "▌")
            placeholder.markdown(full_response)
            st.session_state.messages.append({"role": "assistant", "content": full_response})
        except Exception as e:
            placeholder.error(f"调用失败: {str(e)}")

st.caption(f"当前模型: **{st.session_state.selected_model}** | 自动模式: {'✅' if st.session_state.auto_mode else '❌'}")
