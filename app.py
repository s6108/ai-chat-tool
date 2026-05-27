import streamlit as st
import os
import base64
from openai import OpenAI
from supabase import create_client, Client

st.set_page_config(page_title="Mango AI", page_icon="🥭", layout="centered")

# ====================== Supabase ======================
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

# ====================== 加强固定底部CSS ======================
st.markdown("""
    <style>
        .bottom-bar {
            position: fixed !important;
            bottom: 0 !important;
            left: 0 !important;
            right: 0 !important;
            background: white;
            padding: 12px 15px 35px 15px;
            box-shadow: 0 -4px 25px rgba(0,0,0,0.2);
            z-index: 10000;
            border-top: 1px solid #ddd;
        }
        .main .block-container {
            padding-bottom: 240px !important;
        }
        div[data-testid="stChatInput"] {
            position: fixed !important;
            bottom: 0 !important;
            width: 100% !important;
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
if "current_image" not in st.session_state:
    st.session_state.current_image = None   # 只保存当前问题的图片

DAILY_GUEST_LIMIT = 20

# ====================== 未登录游客模式 ======================
if not st.session_state.user:
    st.title("🥭 Mango AI")
    st.info(f"🔓 游客模式（今日已用 {st.session_state.guest_count}/{DAILY_GUEST_LIMIT} 条）")
    if st.button("登录 / 注册", use_container_width=True):
        st.session_state.show_login = True
    # 登录注册代码（省略，与之前一致）
    # ...

# ====================== 已登录主界面 ======================
if st.session_state.user:
    st.title("🥭 Mango AI")
    st.write(f"欢迎回来，**{st.session_state.user.email}**")

# 侧边栏（省略，与之前一致）
with st.sidebar:
    # ... 保持你之前的侧边栏代码 ...

if st.button("🗑️ 清空对话"):
    st.session_state.messages = []
    st.session_state.current_image = None
    st.rerun()

# 显示聊天记录
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"] if isinstance(msg["content"], str) else "📸 图片")

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

    # 处理图片（只用于当前问题）
    current_image = None
    if uploaded_file:
        b64 = base64.b64encode(uploaded_file.getvalue()).decode()
        current_image = [{"type": "text", "text": prompt or "请描述这张图片"},
                         {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}]
        st.image(uploaded_file, caption="✅ 图片已上传")
        st.session_state.current_image = current_image

    user_message = current_image if current_image else prompt
    st.session_state.messages.append({"role": "user", "content": user_message})

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
