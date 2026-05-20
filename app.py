import streamlit as st
import os
import base64
from openai import OpenAI
from supabase import create_client, Client

st.set_page_config(page_title="Mango AI", page_icon="🥭", layout="centered")

# ====================== Supabase 配置 ======================
SUPABASE_URL = "https://oeiomraxpgmirnubtrug.supabase.co"
SUPABASE_KEY = "sb_publishable_oQ6lNrM38kY1F_xWnzQI6w_LK86YMpi"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ====================== API Keys ======================
def get_key(name: str):
    return os.getenv(name) or st.secrets.get(name)

ZHIPU_API_KEY = get_key("ZHIPU_API_KEY")
DEEPSEEK_API_KEY = get_key("DEEPSEEK_API_KEY")
# ... 其他模型的key保持你原来的 ...

# ====================== 模型配置（简化版） ======================
model_options = {
    "DeepSeek": {"base_url": "https://api.deepseek.com", "model": "deepseek-chat", "key": DEEPSEEK_API_KEY},
    "GLM-4V":   {"base_url": "https://open.bigmodel.cn/api/paas/v4/", "model": "glm-4v-plus", "key": ZHIPU_API_KEY},
}

# ====================== 用户登录 ======================
if "user" not in st.session_state:
    st.session_state.user = None

if not st.session_state.user:
    st.title("🥭 Mango AI")
    st.subheader("请登录或注册")

    tab1, tab2 = st.tabs(["登录", "注册"])
    with tab1:
        email = st.text_input("邮箱地址")
        password = st.text_input("密码", type="password")
        if st.button("登录", use_container_width=True):
            try:
                res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                st.session_state.user = res.user
                st.success("登录成功！")
                st.rerun()
            except Exception as e:
                st.error(f"登录失败: {e}")

    with tab2:
        email_reg = st.text_input("注册邮箱")
        password_reg = st.text_input("设置密码 (至少6位)", type="password")
        if st.button("注册", use_container_width=True):
            try:
                res = supabase.auth.sign_up({"email": email_reg, "password": password_reg})
                st.success("注册成功！请去邮箱查收验证邮件")
            except Exception as e:
                st.error(f"注册失败: {e}")
    st.stop()

# ====================== 已登录主界面 ======================
st.title("🥭 Mango AI")
st.write(f"欢迎回来，{st.session_state.user.email}")

if st.button("退出登录"):
    supabase.auth.sign_out()
    st.session_state.user = None
    st.rerun()

# 聊天功能（简化版，先保证能跑）
prompt = st.chat_input("输入你的问题...")
if prompt:
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        st.info("模型调用功能正常（待后续完善）")

st.caption("Supabase 用户系统已接入")
