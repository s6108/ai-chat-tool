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

# ====================== 固定底部输入栏 CSS ======================
st.markdown("""
    <style>
        .bottom-bar {
            position: fixed !important;
            bottom: 0 !important;
            left: 0 !important;
            right: 0 !important;
            background: white;
            padding: 10px 15px 20px 15px;
            box-shadow: 0 -4px 15px rgba(0,0,0,0.1);
            z-index: 10000;
            border-top: 1px solid #eee;
        }
        .main .block-container {
            padding-bottom: 180px !important;
        }
    </style>
""", unsafe_allow_html=True)

# ====================== 用户登录 ======================
if "user" not in st.session_state:
    st.session_state.user = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "selected_model" not in st.session_state:
    st.session_state.selected_model = "DeepSeek"
if "auto_mode" not in st.session_state:
    st.session_state.auto_mode = True

if not st.session_state.user:
    # 登录页面代码（保持你之前能用的版本）
    st.title("🥭 Mango AI")
    st.subheader("请登录或注册")
    tab1, tab2 = st.tabs(["登录", "注册"])
    # ...（保持你能正常注册登录的代码）...
    st.stop()

# ====================== 主界面 ======================
st.title("🥭 Mango AI")
st.write(f"欢迎回来，**{st.session_state.user.email}**")

# 侧边栏
with st.sidebar:
    if st.button("退出登录"):
        supabase.auth.sign_out()
        st.session_state.user = None
        st.rerun()

    st.link_button("💎 升级高级会员 $7.99/月", 
                   "https://jjyo-ai-chat.lemonsqueezy.com/checkout/buy/ba6ddc8c-7c6f-40e1-b886-019ebc747a0a?lang=en")

    st.markdown("### 模式")
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

# 清空对话
if st.button("🗑️ 清空对话"):
    st.session_state.messages = []
    st.rerun()

# 显示聊天记录
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"] if isinstance(msg["content"], str) else "图片已处理")

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
    # 这里放你的聊天调用逻辑（模型选择、自动模式、流式输出等）
    # 我先给你简化框架，你确认能跑后再补充完整
    st.session_state.messages.append({"role": "user", "content": prompt or "📸 图片"})
    with st.chat_message("assistant"):
        st.info("模型调用中...（待你补充完整逻辑）")

st.caption(f"当前模型: **{st.session_state.selected_model}** | 自动: {'✅' if st.session_state.auto_mode else '❌'}")
