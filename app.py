import streamlit as st
import os
import base64
from openai import OpenAI
from supabase import create_client, Client
from datetime import datetime, timedelta

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

MONTHLY_LIMIT = 2_000_000

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
                st.success("注册成功！请查收邮箱验证邮件")
            except Exception as e:
                st.error(f"注册失败: {e}")
    st.stop()

# ====================== 已登录 ======================
user = st.session_state.user
user_id = user.id

# 获取用户使用量
def get_usage():
    data = supabase.table("user_usage").select("*").eq("user_id", user_id).execute()
    if data.data:
        return data.data[0]
    else:
        supabase.table("user_usage").insert({
            "user_id": user_id,
            "total_tokens": 0,
            "reset_date": (datetime.utcnow() + timedelta(days=30)).isoformat()
        }).execute()
        return get_usage()

usage = get_usage()
total_tokens = usage.get("total_tokens", 0)

# ====================== 侧边栏 ======================
with st.sidebar:
    st.title("🥭 Mango AI")
    st.write(f"👤 {user.email}")
    
    if st.button("退出登录"):
        supabase.auth.sign_out()
        st.session_state.user = None
        st.rerun()

    st.metric("本月 Token 用量", f"{total_tokens:,} / {MONTHLY_LIMIT:,}")

    if total_tokens > MONTHLY_LIMIT * 0.85:
        st.warning("⚠️ 已接近上限，建议合理使用")

    st.link_button("💎 升级高级会员 $7.99/月", 
                   "https://jjyo-ai-chat.lemonsqueezy.com/checkout/buy/ba6ddc8c-7c6f-40e1-b886-019ebc747a0a?lang=en")

# ====================== 主界面 ======================
st.title("🥭 Mango AI")
st.markdown("**6大顶级模型 · 支持图片识别**")

if st.button("🗑️ 清空对话"):
    st.session_state.messages = []
    st.rerun()

# 显示历史消息
for msg in st.session_state.get("messages", []):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"] if isinstance(msg["content"], str) else msg["content"][0]["text"])

# 输入
prompt = st.chat_input("输入你的问题...")
uploaded_file = st.file_uploader("📎 上传图片", type=["png", "jpg", "jpeg"])

# 处理输入
if prompt or uploaded_file is not None:
    if "messages" not in st.session_state:
        st.session_state.messages = []

    has_image = uploaded_file is not None
    text_length = len(prompt) if prompt else 0

    selected_model = "GLM-4V" if has_image else "DeepSeek"

    # 超限处理
    if total_tokens > MONTHLY_LIMIT * 0.9:
        selected_model = "Doubao-Pro"
        st.warning("⚠️ 已接近上限，已切换至最省钱模型")

    # 构建消息
    user_content = prompt or "请描述这张图片"
    if uploaded_file:
        b64 = base64.b64encode(uploaded_file.getvalue()).decode()
        user_content = [{"type": "text", "text": prompt or "请描述这张图片"},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}]

    st.session_state.messages.append({"role": "user", "content": user_content})

    with st.chat_message("user"):
        st.markdown(prompt if prompt else "📸 图片已上传")

    # 调用模型
    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_response = ""
        try:
            cfg = model_options[selected_model]
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

            # 更新 Token 用量
            estimated = int(len(full_response) * 1.5 + text_length)
            new_total = total_tokens + estimated
            supabase.table("user_usage").update({"total_tokens": new_total}).eq("user_id", user_id).execute()

        except Exception as e:
            placeholder.error(f"调用失败: {str(e)}")
            full_response = "抱歉，模型调用出现错误。"

        st.session_state.messages.append({"role": "assistant", "content": full_response})
