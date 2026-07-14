import os
import base64
from pathlib import Path
import streamlit.components.v1 as components
from PIL import Image
from datetime import datetime, timezone, timedelta
import streamlit as st
import secrets
import hashlib
from urllib.parse import urlencode
from types import SimpleNamespace
from openai import OpenAI
from supabase import create_client
from streamlit_js_eval import streamlit_js_eval
from services.chat_service import save_message
from services.device_service import get_device_id
from services.usage_service import (
    FREE_CHAT_LIMIT,
    FREE_IMAGE_LIMIT,
    get_today_usage,
    can_use_chat,
    can_use_image,
    increase_chat_usage,
    increase_image_usage,
)
from streamlit_cookies_manager import EncryptedCookieManager
from services.account_service import get_account_data
from services.subscription_service import get_customer_portal_url
# ============================================================
# Mango AI v2 Stable
# Streamlit + Supabase + Multi-model AI Chat
# ============================================================


# ====================== Page Config ======================
APP_DIR = Path(__file__).resolve().parent
MANGO_ICON_PATH = APP_DIR / "static" / "apple-touch-icon.png"

try:
    mango_page_icon = Image.open(MANGO_ICON_PATH)
except Exception:
    mango_page_icon = "🥭"

st.set_page_config(
    page_title="Mango AI",
    page_icon=mango_page_icon,
    layout="wide",
    initial_sidebar_state="collapsed",
)
components.html(
    """
    <script>
    (() => {
        const parentDocument = window.parent.document;
        const head = parentDocument.head;

        function setLink(rel, href, sizes = "") {
            let link = head.querySelector(`link[rel="${rel}"]`);

            if (!link) {
                link = parentDocument.createElement("link");
                link.setAttribute("rel", rel);
                head.appendChild(link);
            }

            link.setAttribute("href", href);

            if (sizes) {
                link.setAttribute("sizes", sizes);
            }
        }

        setLink(
            "apple-touch-icon",
            "/app/static/apple-touch-icon.png",
            "180x180"
        );

        setLink(
            "apple-touch-icon-precomposed",
            "/app/static/apple-touch-icon.png",
            "180x180"
        );

        setLink(
            "manifest",
            "/app/static/manifest.json"
        );

        let mobileCapable = head.querySelector(
            'meta[name="apple-mobile-web-app-capable"]'
        );

        if (!mobileCapable) {
            mobileCapable = parentDocument.createElement("meta");
            mobileCapable.setAttribute(
                "name",
                "apple-mobile-web-app-capable"
            );
            head.appendChild(mobileCapable);
        }

        mobileCapable.setAttribute("content", "yes");

        let appTitle = head.querySelector(
            'meta[name="apple-mobile-web-app-title"]'
        );

        if (!appTitle) {
            appTitle = parentDocument.createElement("meta");
            appTitle.setAttribute(
                "name",
                "apple-mobile-web-app-title"
            );
            head.appendChild(appTitle);
        }

        appTitle.setAttribute("content", "Mango AI");

        let statusBar = head.querySelector(
            'meta[name="apple-mobile-web-app-status-bar-style"]'
        );

        if (!statusBar) {
            statusBar = parentDocument.createElement("meta");
            statusBar.setAttribute(
                "name",
                "apple-mobile-web-app-status-bar-style"
            );
            head.appendChild(statusBar);
        }

        statusBar.setAttribute("content", "default");
    })();
    </script>
    """,
    height=0,
    width=0,
)


# ====================== Environment Config ======================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY or not SUPABASE_SERVICE_KEY:
    st.error("Supabase 环境变量未配置完整，请检查 Render Environment Variables。")
    st.stop()

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
supabase_admin = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
COOKIE_PASSWORD = os.getenv("COOKIE_PASSWORD")

if not COOKIE_PASSWORD:
    st.error("COOKIE_PASSWORD 环境变量未配置，请检查 Render Environment Variables。")
    st.stop()

cookies = EncryptedCookieManager(
    prefix="mango_ai_",
    password=COOKIE_PASSWORD,
)

if not cookies.ready():
    st.stop()
# ====================== Debug ======================
DEBUG = False
# ====================== Basic Utils ======================
def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()
def generate_remember_token():
    return secrets.token_urlsafe(48)


def hash_remember_token(token: str):
    return hashlib.sha256(token.encode()).hexdigest()


def save_remember_session(user, days=30):
    token = generate_remember_token()
    token_hash = hash_remember_token(token)

    expires_at = (
        datetime.now(timezone.utc) + timedelta(days=days)
    ).isoformat()

    supabase_admin.table("remember_sessions").delete().eq(
        "user_id", user.id
    ).execute()

    supabase_admin.table("remember_sessions").insert(
        {
    "user_id": user.id,
    "email": user.email,
    "token_hash": token_hash,
    "device_id": device_id,
    "expires_at": expires_at,
}
    ).execute()

    cookies["remember_token"] = token

    # 清掉旧 Supabase token，避免 Already Used 冲突
    cookies["access_token"] = ""
    cookies["refresh_token"] = ""
    cookies["login_saved_at"] = now_utc()

    cookies.save()


def restore_login_from_remember():
    try:
        result = (
            supabase_admin.table("remember_sessions")
            .select("*")
            .eq("device_id", device_id)
            .gt("expires_at", now_utc())
            .limit(1)
            .execute()
        )

        if not result.data:
            return None

        saved = result.data[0]

        supabase_admin.table("remember_sessions").update(
            {"last_seen": now_utc()}
        ).eq("id", saved["id"]).execute()

        return SimpleNamespace(
            id=saved.get("user_id"),
            email=saved.get("email") or "用户"
        )

    except Exception as e:
        print(f"Remember restore failed: {e}")
        return None

def clear_remember_session():
    token = cookies.get("remember_token")

    if token:
        token_hash = hash_remember_token(token)
        supabase_admin.table("remember_sessions").delete().eq(
            "token_hash", token_hash
        ).execute()

    cookies["remember_token"] = ""
    cookies["access_token"] = ""
    cookies["refresh_token"] = ""
    cookies["login_saved_at"] = ""
    cookies.save()

    
def get_key(name: str):
    return os.getenv(name)
def save_auth_cookies(session):
    if not session:
        return

    cookies["access_token"] = session.access_token
    cookies["refresh_token"] = session.refresh_token
    cookies["login_saved_at"] = now_utc()
    cookies.save()
def restore_login_from_cookies():
    access_token = cookies.get("access_token")
    refresh_token = cookies.get("refresh_token")
    print("Access exists:", bool(access_token))
    print("Refresh exists:", bool(refresh_token))
    if not refresh_token:
        return None

    try:
        if access_token:
            res = supabase.auth.set_session(access_token, refresh_token)
        else:
            res = supabase.auth.refresh_session(refresh_token)

        if res and res.user:
            if res.session:
                save_auth_cookies(res.session)
            return res.user

    except Exception as e:
        print(f"Cookie restore failed: {e}")
        cookies["access_token"] = ""
        cookies["refresh_token"] = ""
        cookies.save()

    return None

# ====================== Device ID ======================
device_id = get_device_id()
if not device_id:
    st.stop()


# ====================== API Keys ======================
ZHIPU_API_KEY = get_key("ZHIPU_API_KEY")
DEEPSEEK_API_KEY = get_key("DEEPSEEK_API_KEY")
KIMI_API_KEY = get_key("KIMI_API_KEY")
DOUBAO_API_KEY = get_key("DOUBAO_API_KEY")
DASHSCOPE_API_KEY = get_key("DASHSCOPE_API_KEY")


# ====================== Model Config ======================
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


# ====================== Chat Database Functions ======================
def load_messages(session_id: str):
    result = (
        supabase_admin.table("messages")
        .select("*")
        .eq("session_id", session_id)
        .order("created_at", desc=True)
        .limit(100)
        .execute()
    )

    rows = list(reversed(result.data or []))
    return [
        {
            "role": row.get("role", "user"),
            "content": row.get("content", ""),
        }
        for row in rows
    ]


def load_sessions(user_id: str):
    result = (
        supabase_admin.table("chat_sessions")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(30)
        .execute()
    )
    return result.data or []


def create_new_chat(user_id: str):
    result = (
        supabase_admin.table("chat_sessions")
        .insert({"user_id": user_id, "title": "新对话"})
        .execute()
    )
    if not result.data:
        raise RuntimeError("创建新对话失败")
    return result.data[0]["id"]


def delete_chat(session_id: str):
    if not session_id:
        return
    supabase_admin.table("messages").delete().eq("session_id", session_id).execute()
    supabase_admin.table("chat_sessions").delete().eq("id", session_id).execute()


def clear_chat_messages(session_id: str):
    if not session_id:
        return
    supabase_admin.table("messages").delete().eq("session_id", session_id).execute()


def update_chat_title_if_needed(session_id: str, prompt: str):
    if not session_id or not prompt:
        return

    result = (
        supabase_admin.table("chat_sessions")
        .select("title")
        .eq("id", session_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        return

    old_title = result.data[0].get("title") or "新对话"
    if old_title == "新对话":
        new_title = prompt.strip().replace("\n", " ")[:22]
        if new_title:
            (
                supabase_admin.table("chat_sessions")
                .update({"title": new_title})
                .eq("id", session_id)
                .execute()
            )

LEMONSQUEEZY_CHECKOUT_URL = (
    "https://jjyo-ai-chat.lemonsqueezy.com/checkout/buy/ba6ddc8c-7c6f-40e1-b886-019ebc747a0a"
)


def get_premium_checkout_url(user) -> str:
    """生成绑定当前 Mango AI 用户的 LemonSqueezy 付款链接。"""
    params = {
        "lang": "en",
        "checkout[email]": user.email or "",
        "checkout[custom][user_id]": str(user.id),
    }

    separator = "&" if "?" in LEMONSQUEEZY_CHECKOUT_URL else "?"

    return (
        f"{LEMONSQUEEZY_CHECKOUT_URL}"
        f"{separator}{urlencode(params)}"
    )


# ====================== Device / Login Management ======================
def get_user_plan(user_id: str) -> str:
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


def enforce_device_limit(user_id: str, current_device_id: str, plan: str = "free"):
    max_devices = 3 if plan == "premium" else 2

    result = (
        supabase_admin.table("device_sessions")
        .select("*")
        .eq("user_id", user_id)
        .order("last_seen", desc=True)
        .execute()
    )

    devices = result.data or []
    other_devices = [d for d in devices if d.get("device_id") != current_device_id]

    if len(other_devices) >= max_devices:
        for d in other_devices[max_devices - 1:]:
            supabase_admin.table("device_sessions").delete().eq("id", d["id"]).execute()


def save_device_session(user, session, plan: str = "free"):
    if not user or not session:
        return

    supabase_admin.table("device_sessions").upsert(
        {
            "device_id": device_id,
            "user_id": user.id,
            "email": user.email,
            "access_token": session.access_token,
            "refresh_token": session.refresh_token,
            "last_seen": now_utc(),
            "plan": plan,
        },
        on_conflict="device_id",
    ).execute()

    enforce_device_limit(user.id, device_id, plan)


def restore_login_from_device():
    try:
        result = (
            supabase_admin.table("device_sessions")
            .select("*")
            .eq("device_id", device_id)
            .limit(1)
            .execute()
        )

        if not result.data:
            return None

        saved = result.data[0]
        access_token = saved.get("access_token")
        refresh_token = saved.get("refresh_token")
        plan = saved.get("plan") or "free"

        if not refresh_token:
            return None

        try:
            if access_token:
                auth_res = supabase.auth.set_session(access_token, refresh_token)
            else:
                auth_res = supabase.auth.refresh_session(refresh_token)
        except Exception:
            auth_res = supabase.auth.refresh_session(refresh_token)

        if auth_res and auth_res.user:
            if auth_res.session:
                save_auth_cookies(auth_res.session)
                save_device_session(auth_res.user, auth_res.session, plan)

            return auth_res.user

    except Exception as e:
        print(f"Cookie restore failed: {e}")

    return None
# ====================== Session State Init ======================
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
if "new_chat_mode" not in st.session_state:
    st.session_state.new_chat_mode = False
if "new_chat_mode" not in st.session_state:
    st.session_state.new_chat_mode = True
if "page" not in st.session_state:
    st.session_state.page = "chat"
# ====================== Auto Login ======================
if st.session_state.user is None:
    restored_user = restore_login_from_remember()
    if restored_user:
        st.session_state.user = restored_user
        st.session_state.current_session_id = None
        st.session_state.messages = []
        st.session_state.new_chat_mode = True


# ====================== Load Current Chat ======================
if (
    st.session_state.user
    and st.session_state.current_session_id is None
    and not st.session_state.new_chat_mode
):
    try:
        sessions = [s for s in load_sessions(st.session_state.user.id) if s.get("title") != "新对话"]
        if sessions:
            st.session_state.current_session_id = sessions[0]["id"]
            st.session_state.messages = load_messages(st.session_state.current_session_id)
        else:
            st.session_state.current_session_id = None
            st.session_state.messages = []
    except Exception as e:
        st.warning(f"加载历史会话失败：{e}")


# ====================== Login / Register Page ======================
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
                st.session_state.current_session_id = None
                st.session_state.messages = []
                st.session_state.new_chat_mode = True
                if res.session:
                    
                    save_remember_session(res.user)
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


# ====================== Main Page ======================
st.title("🥭 Mango AI")

user_email = getattr(st.session_state.user, "email", "用户")
st.write(f"欢迎回来，**{user_email}**")

# ====================== Sidebar ======================
premium_checkout_url = get_premium_checkout_url(
    st.session_state.user
)

with st.sidebar:
    if st.button("退出登录", use_container_width=True):
        try:
            supabase_admin.table("device_sessions").delete().eq("device_id", device_id).execute()
            supabase.auth.sign_out()
            cookies["access_token"] = ""
            cookies["refresh_token"] = ""
            cookies.save()
        except Exception:
            pass

        st.session_state.user = None
        st.session_state.messages = []
        st.session_state.current_session_id = None
        st.session_state.processing = False
        st.rerun()
    # ====================== Plan and Daily Usage ======================

    with st.expander("👤 My Account", expanded=False):
        account = get_account_data(
            supabase_admin,
            st.session_state.user,
        )

        st.caption("Email")
        st.write(account["email"])

        st.caption("当前套餐")

        if account["is_premium"]:
            st.success("💎 Premium")
        else:
            st.info("🆓 Free")
        st.caption("今日使用")

        if account["is_premium"]:
            st.markdown("💬 **今日聊天：无限**")
            st.markdown("🖼️ **今日识图：无限**")

        else:
            try:
                today_usage = get_today_usage(
                    supabase_admin,
                    st.session_state.user.id,
                )

                chat_count = int(
                    today_usage.get("chat_count", 0)
                )
                image_count = int(
                    today_usage.get("image_count", 0)
                )

                chat_remaining = max(
                    FREE_CHAT_LIMIT - chat_count,
                    0,
                )
                image_remaining = max(
                    FREE_IMAGE_LIMIT - image_count,
                    0,
                )

                st.markdown(
                    f"💬 **今日聊天："
                    f"{chat_count} / {FREE_CHAT_LIMIT}**"
                )
                st.progress(
                    min(
                        chat_count / FREE_CHAT_LIMIT,
                        1.0,
                    )
                )
                st.caption(
                    f"剩余 {chat_remaining} 次"
                )

                st.markdown(
                    f"🖼️ **今日识图："
                    f"{image_count} / {FREE_IMAGE_LIMIT}**"
                )
                st.progress(
                    min(
                        image_count / FREE_IMAGE_LIMIT,
                        1.0,
                    )
                )
                st.caption(
                    f"剩余 {image_remaining} 次"
                )

            except Exception as usage_error:
                print(
                    "Sidebar usage load failed: "
                    f"{usage_error}"
                )
                st.caption("暂时无法读取今日用量")
        st.caption("订阅状态")
        st.write(
            account["status"]
            .replace("_", " ")
            .title()
        )

        if (
            account["is_premium"]
            and account["period_end_display"] != "—"
        ):
            if account["status"] == "cancelled":
                st.caption("Premium 有效期至")
            else:
                st.caption("下次续费 / 当前周期结束")

            st.write(account["period_end_display"])

        if (
            account["is_premium"]
            and account["status"] == "cancelled"
        ):
            st.warning(
                "已取消自动续费，Premium 将保留到当前付费周期结束。"
            )

        if account["is_premium"]:
            subscription_id = account.get("subscription_id")

            if not subscription_id:
                st.warning("暂时无法找到订阅记录，请联系支持。")

            else:
                if st.button(
                    "💳 获取订阅管理链接",
                    use_container_width=True,
                    key="load_customer_portal",
                ):
                    with st.spinner("正在连接订阅管理中心..."):
                        portal_url = get_customer_portal_url(
                            subscription_id
                        )

                    if portal_url:
                        st.session_state.customer_portal_url = (
                            portal_url
                        )
                        st.session_state.portal_subscription_id = (
                            subscription_id
                        )
                    else:
                        st.error(
                            "暂时无法打开订阅管理中心，请稍后重试。"
                        )

                saved_portal_url = st.session_state.get(
                    "customer_portal_url"
                )
                saved_subscription_id = st.session_state.get(
                    "portal_subscription_id"
                )

                if (
                    saved_portal_url
                    and saved_subscription_id == subscription_id
                ):
                    st.link_button(
                        "💳 打开订阅管理",
                        saved_portal_url,
                        use_container_width=True,
                    )

        else:
            # 防止用户降级后继续显示旧的 Portal 链接
            st.session_state.pop(
                "customer_portal_url",
                None,
            )
            st.session_state.pop(
                "portal_subscription_id",
                None,
            )

            st.link_button(
                "🚀 升级 Premium",
                premium_checkout_url,
                use_container_width=True,
            )

    st.markdown("### 模式选择")

    if st.button("🔄 自动模式" if st.session_state.auto_mode else "🔧 手动模式", use_container_width=True):
        st.session_state.auto_mode = not st.session_state.auto_mode
        st.rerun()

    if not st.session_state.auto_mode:
        st.markdown("### 选择模型")
        for model_name in model_options.keys():
            label = "🔴 " + model_name if st.session_state.selected_model == model_name else "⚪ " + model_name
            if st.button(label, key=f"btn_model_{model_name}", use_container_width=True):
                st.session_state.selected_model = model_name
                st.rerun()

    st.markdown("---")
    st.markdown("### 历史会话")

    if st.button("✏️ 新建聊天", use_container_width=True):
        st.session_state.new_chat_mode = True
        st.session_state.page = "chat"
        st.session_state.current_session_id = None
        st.session_state.messages = []
        st.session_state.uploader_key += 1
        st.session_state.processing = False
        st.rerun()

    sessions = [s for s in load_sessions(st.session_state.user.id) if s.get("title") != "新对话"]

    for s in sessions:
        title = s.get("title", "新对话")
        session_id = s["id"]

        label = title[:22]
        if len(title) > 22:
            label += "..."
        if session_id == st.session_state.current_session_id:
            label = "🔴 " + label

        if st.button(label, key=f"open_session_{session_id}", use_container_width=True):
            st.session_state.current_session_id = session_id
            st.session_state.messages = load_messages(session_id)
            st.session_state.new_chat_mode = False
            st.session_state.uploader_key += 1
            st.session_state.processing = False
            st.rerun()

    if st.session_state.current_session_id:
        st.markdown("---")
        if st.button("🗑 删除当前聊天", use_container_width=True):
            delete_chat(st.session_state.current_session_id)
            remaining_sessions = [s for s in load_sessions(st.session_state.user.id) if s.get("title") != "新对话"]

            if remaining_sessions:
                st.session_state.current_session_id = remaining_sessions[0]["id"]
                st.session_state.messages = load_messages(remaining_sessions[0]["id"])
            else:
                st.session_state.current_session_id = None
                st.session_state.messages = []

            st.session_state.uploader_key += 1
            st.session_state.processing = False
            st.rerun()
        if DEBUG:

            st.markdown("---")
            st.subheader("🔧 Debug")

            st.write("Device ID:", device_id)

            st.write(
                "Access Cookie:",
                "✅" if cookies.get("access_token") else "❌"
            )

            st.write(
                "Refresh Cookie:",
                "✅" if cookies.get("refresh_token") else "❌"
            )

            st.write(
                "Login Saved:",
                cookies.get("login_saved_at")
            )

            st.write(
                "User:",
                getattr(st.session_state.user, "email", None)
            )

            st.write(
                "Current Session:",
                st.session_state.current_session_id
            )

            st.write(
                "Processing:",
                st.session_state.processing
            )

# ====================== Clear Current Messages ======================
if st.button("🗑️ 清空当前对话"):
    if st.session_state.current_session_id:
        clear_chat_messages(st.session_state.current_session_id)

    st.session_state.messages = []
    st.session_state.uploader_key += 1
    st.session_state.processing = False
    st.rerun()


# ====================== Display Messages ======================
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        content = msg.get("content", "")
        if isinstance(content, str):
            st.markdown(content)
        else:
            st.markdown("📸 图片已上传")


# ====================== Upload + Chat Input ======================
uploaded_file = st.file_uploader(
    "上传图片",
    type=["png", "jpg", "jpeg"],
    key=f"upload_{st.session_state.uploader_key}",
)

prompt = st.chat_input("输入你的问题...")


# ====================== Process User Input ======================
if prompt:
    user_id = st.session_state.user.id
    user_plan = get_user_plan(user_id) or "free"
    user_plan = str(user_plan).lower()
    
    # 先检查文字聊天额度
    if not can_use_chat(supabase_admin, user_id, user_plan):
        st.error("今日免费聊天额度已用完。升级 Premium 可继续无限使用。")
        st.link_button(
            "🚀 升级 Premium",
            premium_checkout_url,
            use_container_width=True,
        )
        st.stop()

    # 本次包含图片时，再检查图片额度
    if uploaded_file and not can_use_image(
        supabase_admin,
        user_id,
        user_plan,
    ):
        st.error("今日免费图片识别额度已用完。升级 Premium 可继续使用。")
        st.link_button(
            "🚀 升级 Premium",
            premium_checkout_url,
            use_container_width=True,
        )
        st.stop()

    st.session_state.processing = True

if st.session_state.processing:
    if not prompt:
        st.session_state.processing = False
        st.stop()

    if st.session_state.current_session_id is None:
        st.session_state.current_session_id = create_new_chat(st.session_state.user.id)
        st.session_state.messages = []
        st.session_state.new_chat_mode = False
    user_content = prompt

    if uploaded_file:
        b64 = base64.b64encode(uploaded_file.getvalue()).decode()
        user_content = [
            {"type": "text", "text": prompt or "请描述这张图片"},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
        ]

    st.session_state.messages.append({"role": "user", "content": user_content})

    display_user_text = prompt if prompt else "📸 图片已上传"
    save_message(st.session_state.current_session_id, "user", display_user_text)
    update_chat_title_if_needed(st.session_state.current_session_id, prompt)

    with st.chat_message("user"):
        st.markdown(display_user_text)

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
                placeholder.error(f"{st.session_state.selected_model} 的 API Key 未配置。")
                st.session_state.processing = False
                st.stop()

            client = OpenAI(base_url=cfg["base_url"], api_key=cfg["key"])

            if st.session_state.selected_model == "GLM-4V":
                api_messages = st.session_state.messages
            else:
                api_messages = [m for m in st.session_state.messages if isinstance(m.get("content"), str)]

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

            st.session_state.messages.append({"role": "assistant", "content": full_response})
            save_message(st.session_state.current_session_id, "assistant", full_response)
            # 只有模型成功返回后才扣除额度
            try:
                user_id = st.session_state.user.id
                user_plan = get_user_plan(user_id) or "free"
                user_plan = str(user_plan).lower()

                if user_plan != "premium":
                    increase_chat_usage(supabase_admin, user_id)

                    if uploaded_file:
                        increase_image_usage(supabase_admin, user_id)

            except Exception as usage_error:
                # 用量统计失败不能影响用户已经得到的回答
                print(f"Usage update failed: {usage_error}")
            st.session_state.processing = False

            if uploaded_file:
                st.session_state.uploader_key += 1
                st.session_state.selected_model = "DeepSeek"
                st.session_state.messages = [
                    m for m in st.session_state.messages
                    if isinstance(m.get("content"), str)
                ]

            # 每次成功回答后刷新页面，让侧边栏用量立即更新
            st.rerun()

        except Exception as e:
            st.session_state.processing = False
            placeholder.error(f"调用失败: {str(e)}")


# ====================== Status ======================
st.caption(
    f"当前模型: **{st.session_state.selected_model}** | 自动模式: {'✅' if st.session_state.auto_mode else '❌'}"
)
