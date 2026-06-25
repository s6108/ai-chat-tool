mport streamlit as st
import os
import base64
from datetime import datetime, timezone

from openai import OpenAI
from supabase import create_client
from streamlit_js_eval import streamlit_js_eval


# ====================== 页面配置 ======================
st.set_page_config(page_title="Mango AI", page_icon="🥭", layout="centered")


# ====================== Supabase 配置 ======================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY or not SUPABASE_SERVICE_KEY:
    st.error("Supabase 环境变量未配置完整，请检查 Render Environment Variables。")
    st.stop()

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
supabase_admin = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


# ====================== 工具函数 ======================
def now_utc():
    return datetime.now(timezone.utc).isoformat()


def get_key(name: str):
    return os.getenv(name)


# ====================== 获取设备 ID ======================
device_id = streamlit_js_eval(
    js_expressions="""
    let id = localStorage.getItem("mango_device_id");
    if (!id) {
        id = crypto.randomUUID();
        localStorage.setItem("mango_device_id", id);
    }
    id;
    """,
    key="get_device_id",
)

if not device_id:
    st.stop()


# ====================== API Keys ======================
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


# ====================== 数据库函数 ======================
def load_messages(session_id):
    msgs = (
        supabase_admin.table("messages")
        .select("*")
        .eq("session_id", session_id)
        .order("created_at", desc=True)
        .limit(100)
        .execute()
    )

    return [
        {"role": m["role"], "content": m["content"]}
        for m in reversed(msgs.data or [])
    ]


def create_new_chat(user_id):
    new_session = (
        supabase_admin.table("chat_sessions")
        .insert(
            {
                "user_id": user_id,
                "title": "新对话",
            }
        )
        .execute()
    )
    return new_session.data[0]["id"]


def load_sessions(user_id):
    sessions = (
        supabase_admin.table("chat_sessions")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(30)
        .execute()
    )

    return sessions.data or []


def delete_chat(session_id):
    supabase_admin.table("messages").delete().eq("session_id", session_id).execute()
    supabase_admin.table("chat_sessions").delete().eq("id", session_id).execute()


def update_chat_title_if_needed(session_id, prompt):
    if not session_id or not prompt:
        return

    current = (
        supabase_admin.table("chat_sessions")
        .select("title")
        .eq("id", session_id)
        .limit(1)
        .execute()
    )

    if current.data and current.data[0].get("title") == "新对话":
        new_title = prompt.strip()[:22]
        if new_title:
            supabase_admin.table("chat_sessions").update(
                {"title": new_title}
            ).eq("id", session_id).execute()


# ====================== 设备管理 ======================
def get_user_plan(user_id):
    result = (
        supabase_admin.table("device_sessions")
        .select("plan")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )

    if result.data:
        return result.data[0].get("plan") or "free"

    return "free"


def enforce_device_limit(user_id, current_device_id, plan="free"):
    max_devices = 3 if plan == "premium" else 1

    devices = (
        supabase_admin.table("device_sessions")
        .select("*")
        .eq("user_id", user_id)
        .order("last_seen", desc=True)
        .execute()
    )

    other_devices = [
        d for d in (devices.data or [])
        if d.get("device_id") != current_device_id
    ]

    if len(other_devices) >= max_devices:
        for d in other_devices[max_devices - 1:]:
            supabase_admin.table("device_sessions").delete().eq(
                "id", d["id"]
            ).execute()


def save_device_session(user, session, plan="free"):
    if not user or not session:
        return

    supabase_admin.table("device_sessions").upsert(
        {
            "device_id": device_id,
            "user_id": user.id,
            "email": user.email,
            "refresh_token": session.refresh_token,
            "last_seen": now_utc(),
            "plan": plan,
        },
        on_conflict="device_id",
    ).execute()

    enforce_device_limit(user.id, device_id, plan)


# ====================== Session State 初始化 ======================
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
if "current_session_id" not in st.session_state:
    st.session_state.current_session_id = None
if "processing" not in st.session_state:
    st.session_state.processing = False


# ====================== 自动恢复登录 ======================
if st.session_state.user is None:
    try:
        result = (
            supabase_admin.table("device_sessions")
            .select("*")
            .eq("device_id", device_id)
            .limit(1)
            .execute()
        )

        if result.data:
            saved_session = result.data[0]
            refresh_token = saved_session.get("refresh_token")
            plan = saved_session.get("plan") or "free"

            if refresh_token:
                auth_res = supabase.auth.refresh_session(refresh_token)

                if auth_res and auth_res.user:
                    st.session_state.user = auth_res.user

                    if auth_res.session:
                        save_device_session(
                            auth_res.user,
                            auth_res.session,
                            plan,
                        )

    except Exception:
        try:
            supabase_admin.table("device_sessions").delete().eq(
                "device_id", device_id
            ).execute()
        except Exception:
            pass


# ====================== 加载当前聊天会话 ======================
if st.session_state.user and st.session_state.current_session_id is None:
    try:
        sessions = [
            s for s in load_sessions(st.session_state.user.id)
            if s.get("title") != "新对话"
        ]

        if sessions:
            st.session_state.current_session_id = sessions[0]["id"]
            st.session_state.messages = load_messages(st.session_state.current_session_id)
        else:
            st.session_state.current_session_id = None
            st.session_state.messages = []

    except Exception as e:
        st.warning(f"加载历史会话失败：{e}")


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

                if res.session:
                    plan = get_user_plan(res.user.id)
                    save_device_session(res.user, res.session, plan)

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


# ====================== 主界面 ======================
st.title("🥭 Mango AI")
st.write(f"欢迎回来，**{st.session_state.user.email}**")


# ====================== 侧边栏 ======================
with st.sidebar:
    if st.button("退出登录", use_container_width=True):
        try:
            supabase_admin.table("device_sessions").delete().eq(
                "device_id", device_id
            ).execute()
            supabase.auth.sign_out()
        except Exception:
            pass

        st.session_state.user = None
        st.session_state.messages = []
        st.session_state.current_session_id = None
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

    st.markdown("---")
    st.markdown("### 历史会话")

    if st.button("✏️ 新建聊天", use_container_width=True):
        st.session_state.current_session_id = None
        st.session_state.messages = []
        st.session_state.uploader_key += 1
        st.rerun()

    sessions = [
        s for s in load_sessions(st.session_state.user.id)
        if s.get("title") != "新对话"
    ]

    for s in sessions:
        title = s.get("title", "新对话")
        session_id = s["id"]

        label = title[:22]
        if session_id == st.session_state.current_session_id:
            label = "🔴 " + label

        if st.button(label, key=f"open_{session_id}", use_container_width=True):
            st.session_state.current_session_id = session_id
            st.session_state.messages = load_messages(session_id)
            st.session_state.uploader_key += 1
            st.rerun()


# ====================== 清空当前对话 ======================
if st.button("🗑️ 清空当前对话"):
    if st.session_state.current_session_id:
        supabase_admin.table("messages").delete().eq(
            "session_id", st.session_state.current_session_id
        ).execute()

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
if prompt:
    st.session_state.processing = True

if st.session_state.processing:
    if st.session_state.current_session_id is None:
        st.session_state.current_session_id = create_new_chat(st.session_state.user.id)
        st.session_state.messages = []

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

    if st.session_state.current_session_id:
        supabase_admin.table("messages").insert(
            {
                "session_id": st.session_state.current_session_id,
                "role": "user",
                "content": prompt or "📸 图片已上传",
            }
        ).execute()

        update_chat_title_if_needed(
            st.session_state.current_session_id,
            prompt,
        )

    with st.chat_message("user"):
        st.markdown(prompt if prompt else "📸 图片已上传")

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
                st.session_state.processing = False
                st.stop()

            client = OpenAI(
                base_url=cfg["base_url"],
                api_key=cfg["key"],
            )

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

            if st.session_state.current_session_id:
                supabase_admin.table("messages").insert(
                    {
                        "session_id": st.session_state.current_session_id,
                        "role": "assistant",
                        "content": full_response,
                    }
                ).execute()

            st.session_state.processing = False

            if uploaded_file:
                st.session_state.uploader_key += 1
                st.session_state.selected_model = "DeepSeek"
                st.session_state.messages = [
                    m for m in st.session_state.messages
                    if isinstance(m["content"], str)
                ]
                st.rerun()

        except Exception as e:
            st.session_state.processing = False
            placeholder.error(f"调用失败: {str(e)}")


# ====================== 状态栏 ======================
st.caption(
    f"当前模型: **{st.session_state.selected_model}** | 自动模式: {'✅' if st.session_state.auto_mode else '❌'}"
)
