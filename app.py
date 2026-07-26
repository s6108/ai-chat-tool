import base64
import hashlib
import json
import secrets
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlencode

import streamlit as st
import streamlit.components.v1 as components
from openai import OpenAI
from PIL import Image
from services.cookie_service import (
    create_cookie_manager,
    cookies_ready,
    save_cookies,
    get_cookie,
    set_cookie,
    delete_cookie,
)
from streamlit_js_eval import streamlit_js_eval
from supabase import create_client

from config import (
    COOKIE_PASSWORD,
    DASHSCOPE_API_KEY,
    DEEPSEEK_API_KEY,
    DOUBAO_API_KEY,
    KIMI_API_KEY,
    SUPABASE_KEY,
    SUPABASE_SERVICE_KEY,
    SUPABASE_URL,
    ZHIPU_API_KEY,
    OPENAI_API_KEY,
    AUTO_NEW_CHAT_AFTER_MINUTES,
)
from services.account_service import get_account_data
from services.chat_service import save_message
from services.device_service import get_device_id
from services.history_service import (
    clear_chat_messages,
    create_new_chat,
    delete_chat,
    load_messages,
    load_sessions,
    update_chat_title_if_needed,
)
from services.subscription_service import get_customer_portal_url
from services.usage_service import (
    FREE_CHAT_LIMIT,
    FREE_IMAGE_LIMIT,
    can_use_chat,
    can_use_image,
    get_today_usage,
    increase_chat_usage,
    increase_image_usage,
)
from services.remember_service import (
    clear_remember_session,
    restore_login_from_cookies,
    restore_login_from_remember,
    save_auth_cookies,
    save_remember_session,
    save_last_activity,
    load_last_activity,
    is_chat_activity_expired,
)

from services.search_router import should_search
from services.search_service import search_web, format_search_results
from services.date_service import (
    get_search_query,
    build_date_prompt,
)
from services.search_planner import plan_search
from services.search_evaluator import evaluate_search_results


from ui.chat_messages import render_chat_messages, render_user_content
from ui.sidebar import render_sidebar_placeholder
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


if not SUPABASE_URL or not SUPABASE_KEY or not SUPABASE_SERVICE_KEY:
    st.error("Supabase 环境变量未配置完整，请检查 Render Environment Variables。")
    st.stop()

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
supabase_admin = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


if not COOKIE_PASSWORD:
    st.error("COOKIE_PASSWORD 环境变量未配置，请检查 Render Environment Variables。")
    st.stop()

cookies = create_cookie_manager()

if not cookies_ready(cookies):
    st.stop()
# ====================== Debug ======================
DEBUG = False
# ====================== Basic Utils ======================
def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()

# ====================== Device ID ======================
device_id = get_device_id()
if not device_id:
    st.stop()

# ====================== Model Config ======================
model_options = {
    "DeepSeek": {
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-v4-flash",
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
    "ChatGPT": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-5.4-mini",
        "key": OPENAI_API_KEY,
    }
}

MODEL_ICONS = {
    "DeepSeek": "🔴",
    "GLM-4V": "🟠",
    "GLM-4": "🟡",
    "Kimi": "🔵",
    "Doubao-Pro": "🟢",
    "Qwen": "🟣",
    "ChatGPT": "⚫", 
}

MODEL_SELECTOR_OPTIONS = [
    "🔄 自动模式",
    "🔴 DeepSeek",
    "🟠 GLM-4V",
    "🟡 GLM-4",
    "🔵 Kimi",
    "🟢 Doubao-Pro",
    "🟣 Qwen",
    "⚫ ChatGPT",
]

MODEL_LABEL_TO_NAME = {
    "🔴 DeepSeek": "DeepSeek",
    "🟠 GLM-4V": "GLM-4V",
    "🟡 GLM-4": "GLM-4",
    "🔵 Kimi": "Kimi",
    "🟢 Doubao-Pro": "Doubao-Pro",
    "🟣 Qwen": "Qwen",
    "⚫ ChatGPT": "ChatGPT",
}
# ====================== Chat Database Functions ======================
def handle_model_selector_change():
    selected_label = st.session_state.model_selector

    if selected_label == "🔄 自动模式":
        st.session_state.auto_mode = True
        return

    selected_model = MODEL_LABEL_TO_NAME.get(
        selected_label
    )

    if selected_model:
        st.session_state.auto_mode = False
        st.session_state.selected_model = selected_model






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
                save_auth_cookies(
                    cookies,
                    auth_res.session,
                    now_utc,
                )
                save_device_session(auth_res.user, auth_res.session, plan)

            return auth_res.user

    except Exception as e:
        print(f"Cookie restore failed: {e}")

    return None
# ====================== Session State Init ====================== 

def get_chat_id_from_url():
    """读取 URL 中保存的当前聊天 ID。"""
    chat_id = st.query_params.get("chat")

    if not chat_id:
        return None

    return str(chat_id).strip() or None


def remove_chat_id_from_url():
    """只删除 chat 参数，保留 URL 中的其他参数。"""
    params = st.query_params.to_dict()
    params.pop("chat", None)
    st.query_params.from_dict(params)


if "user" not in st.session_state:
    st.session_state.user = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "manual_logout" not in st.session_state:
    st.session_state.manual_logout = False
if "selected_model" not in st.session_state:
    st.session_state.selected_model = "DeepSeek"
if "auto_mode" not in st.session_state:
    st.session_state.auto_mode = True
if "auth_checked" not in st.session_state:
    st.session_state.auth_checked = False
if "model_selector" not in st.session_state:
    if st.session_state.auto_mode:
        st.session_state.model_selector = "🔄 自动模式"
    else:
        current_icon = MODEL_ICONS.get(
            st.session_state.selected_model,
            "🤖",
        )
        st.session_state.model_selector = (
            f"{current_icon} "
            f"{st.session_state.selected_model}"
        )
if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0
if "current_session_id" not in st.session_state:
    st.session_state.current_session_id = get_chat_id_from_url()
if "processing" not in st.session_state:
    st.session_state.processing = False
if "new_chat_mode" not in st.session_state:
    st.session_state.new_chat_mode = False
if "new_chat_mode" not in st.session_state:
    st.session_state.new_chat_mode = True
if "page" not in st.session_state:
    st.session_state.page = "chat"

# ==================== Auto Login ====================

restored_user = None

manual_logout_marker = (
    get_cookie(cookies, "manual_logout_marker") == "1"
)

print("主动退出标记：", manual_logout_marker)

if (
    st.session_state.user is None
    and not st.session_state.auth_checked
    and not manual_logout_marker
):
    st.session_state.auth_checked = True

    restored_user = restore_login_from_cookies(
        cookies,
        supabase,
        now_utc,
    )

    if restored_user is None:
        restored_user = restore_login_from_remember(
            cookies,
            device_id,
        )

if restored_user:
    st.session_state.user = restored_user

    
if restored_user:
    st.session_state.user = restored_user

    restored_chat_id = get_chat_id_from_url()
    last_activity = load_last_activity(cookies)

    activity_expired = is_chat_activity_expired(
        last_activity,
        AUTO_NEW_CHAT_AFTER_MINUTES,
    )

    if activity_expired:
        st.session_state.current_session_id = None
        st.session_state.messages = []
        st.session_state.new_chat_mode = True
        st.session_state.processing = False

        remove_chat_id_from_url()

        print(
            "🆕 距离上次活动超过 "
            f"{AUTO_NEW_CHAT_AFTER_MINUTES} 分钟，"
            "进入新聊天页面"
        )

    else:
        st.session_state.current_session_id = restored_chat_id
        st.session_state.messages = []
        st.session_state.new_chat_mode = (
            restored_chat_id is None
        )

        print("↩️ 用户仍在活动期内，恢复原聊天")

# ================= Load Current Chat =================

if st.session_state.user:
    try:
        sessions = [
            session
            for session in load_sessions(st.session_state.user.id)
            if session.get("title") != "新对话"
        ]

        valid_session_ids = {
            str(session["id"])
            for session in sessions
            if session.get("id")
        }

        current_session_id = st.session_state.current_session_id

        # URL 或 Session State 中已有当前聊天 ID
        if current_session_id:
            current_session_id = str(current_session_id)

            # 安全检查：只能恢复属于当前用户的聊天
            if current_session_id in valid_session_ids:
                if not st.session_state.messages:
                    st.session_state.messages = load_messages(
                        current_session_id
                    )

                st.session_state.current_session_id = current_session_id
                st.session_state.new_chat_mode = False

            else:
                # URL 中的会话不存在，或不属于当前用户
                st.session_state.current_session_id = None
                st.session_state.messages = []
                st.session_state.new_chat_mode = True
                remove_chat_id_from_url()

        # 没有指定聊天，而且用户不是主动处于“新聊天”模式
        elif not st.session_state.new_chat_mode and sessions:
            latest_session_id = str(sessions[0]["id"])

            st.session_state.current_session_id = latest_session_id
            st.session_state.messages = load_messages(
                latest_session_id
            )

            st.query_params["chat"] = latest_session_id

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

                # 用户主动重新登录，解除此前的退出标记
                delete_cookie(cookies, "manual_logout_marker")
                save_cookies(cookies)

                st.session_state.auth_checked = True
                st.session_state.current_session_id = None
                st.session_state.messages = []
                st.session_state.new_chat_mode = True
                if res.session:
                    save_auth_cookies(
                        cookies,
                        res.session,
                        now_utc,
                    )

                    # 临时跳过 remember session 测试
                    try:
                        pass
                    except Exception as remember_error:
                        print(f"Remember session save failed: {remember_error}")

                    

                    try:
                        plan = get_user_plan(res.user.id)
                        save_device_session(res.user, res.session, plan)
                    except Exception as device_error:
                        print(f"Device session update failed: {device_error}")
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
# 用户从付款页返回 Mango AI 时，自动刷新一次页面，
# 以便重新读取最新的订阅状态。
components.html(
    """
    <script>
    (() => {
        const parentWindow = window.parent;
        const parentDocument = parentWindow.document;

        if (parentWindow.__mangoVisibilityRefreshInstalled) {
            return;
        }

        parentWindow.__mangoVisibilityRefreshInstalled = true;

        let wasHidden = parentDocument.hidden;

        parentDocument.addEventListener(
            "visibilitychange",
            () => {
                if (parentDocument.hidden) {
                    wasHidden = true;
                    return;
                }

                if (wasHidden) {
                    wasHidden = false;

                    // 稍等 Webhook 完成数据库更新后再刷新。
                    setTimeout(() => {
                        parentWindow.location.reload();
                    }, 2500);
                }
            }
        );
    })();
    </script>
    """,
    height=0,
)

premium_checkout_url = get_premium_checkout_url(
    st.session_state.user
)
render_sidebar_placeholder()
with st.sidebar:
    if st.button("退出登录", use_container_width=True):
        # 阻止本次 rerun 立即恢复
        st.session_state.auth_checked = True

        # 1. 删除设备会话
        try:
            supabase_admin.table("device_sessions").delete().eq(
                "device_id",
                device_id,
            ).execute()
        except Exception as device_error:
            print(f"删除设备登录记录失败：{device_error}")

        # 2. 撤销该设备的长期登录授权
        try:
            supabase_admin.table("remember_sessions").delete().eq(
                "device_id",
                device_id,
            ).execute()

            print("已删除该设备的 remember_sessions 记录")

        except Exception as remember_error:
            print(f"删除长期登录记录失败：{remember_error}")

        # 3. 注销 Supabase 当前会话
        try:
            supabase.auth.sign_out()
        except Exception as signout_error:
            print(f"Supabase 退出失败：{signout_error}")

        # 4. 清除登录 Cookie
        try:
            clear_remember_session(cookies)
        except Exception as cookie_error:
            print(f"清除登录 Cookie 失败：{cookie_error}")

        # 5. 退出标记暂时保留，作为辅助保护
        try:
            set_cookie(cookies, "manual_logout_marker", "1")
            save_cookies(cookies)
        except Exception as marker_error:
            print(f"写入退出标记失败：{marker_error}")

        # 6. 清理页面状态
        st.session_state.user = None
        st.session_state.messages = []
        st.session_state.current_session_id = None
        st.session_state.new_chat_mode = True
        st.session_state.processing = False

        remove_chat_id_from_url()
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
                portal_url = st.session_state.get(
                    "customer_portal_url"
                )
                cached_subscription_id = st.session_state.get(
                    "portal_subscription_id"
                )

                # 当前订阅尚未获取链接时，自动请求一次。
                if (
                    not portal_url
                    or cached_subscription_id != subscription_id
                ):
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

                if portal_url:
                    st.link_button(
                        "💳 管理订阅",
                        portal_url,
                        use_container_width=True,
                    )
                else:
                    st.error(
                        "暂时无法连接订阅管理中心，请稍后重试。"
                    )

        else:
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
    


    st.markdown("---")
    st.markdown("### 历史会话")

    if st.button("✏️ 新建聊天", use_container_width=True):
        st.session_state.new_chat_mode = True
        st.session_state.page = "chat"
        st.session_state.current_session_id = None
        st.session_state.messages = []
        st.session_state.uploader_key += 1
        st.session_state.processing = False
        remove_chat_id_from_url()
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

        if st.button(
            label,
            key=f"open_session_{session_id}",
            use_container_width=True,
        ):
            st.session_state.current_session_id = session_id
            st.session_state.messages = load_messages(session_id)
            st.session_state.new_chat_mode = False
            st.query_params["chat"] = str(session_id)

            # 用户主动打开历史会话，也属于一次有效活动
            save_last_activity(cookies)
            save_cookies(cookies)

            st.session_state.uploader_key += 1
            st.session_state.processing = False
            st.rerun()

    if st.session_state.current_session_id:
        st.markdown("---")
        if st.button("🗑 删除当前聊天", use_container_width=True):
            delete_chat(st.session_state.current_session_id)
            remaining_sessions = [s for s in load_sessions(st.session_state.user.id) if s.get("title") != "新对话"]

            if remaining_sessions:
                next_session_id = remaining_sessions[0]["id"]

                st.session_state.current_session_id = next_session_id
                st.session_state.messages = load_messages(next_session_id)
                st.session_state.new_chat_mode = False

                st.query_params["chat"] = str(next_session_id)
            else:
                st.session_state.current_session_id = None
                st.session_state.messages = []
                st.session_state.new_chat_mode = True

                remove_chat_id_from_url()

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
render_chat_messages(
    st.session_state.messages
)

# ====================== Upload + Chat Input ======================

st.selectbox(
    "选择模型",
    MODEL_SELECTOR_OPTIONS,
    key="model_selector",
    on_change=handle_model_selector_change,
    label_visibility="collapsed",
)

submission = st.chat_input(
    "输入你的问题...",
    accept_file=True,
    file_type=["png", "jpg", "jpeg"],
    max_upload_size=20,
    key="main_chat_input",
)
prompt = ""
uploaded_file = None

if submission:
    prompt = submission.text or ""

    if submission.files:
        uploaded_file = submission.files[0]


# ====================== Process User Input ======================
if submission and (prompt or uploaded_file):
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
        new_session_id = create_new_chat(
            st.session_state.user.id
        )

        st.session_state.current_session_id = new_session_id
        st.session_state.new_chat_mode = False
        st.session_state.messages = []
        
    user_content = prompt

    if uploaded_file:
        b64 = base64.b64encode(uploaded_file.getvalue()).decode()
        user_content = [
            {"type": "text", "text": prompt or "请描述这张图片"},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
        ]

    st.session_state.messages.append({"role": "user", "content": user_content})

    display_user_text = prompt if prompt else "📸 图片已上传"
    content_to_save = (
        json.dumps(user_content, ensure_ascii=False)
        if isinstance(user_content, list)
        else user_content
    )

    save_message(
        st.session_state.current_session_id,
        "user",
        content_to_save,
    )
    update_chat_title_if_needed(st.session_state.current_session_id, prompt)
    

    with st.chat_message("user"):
        render_user_content(user_content)

    if st.session_state.auto_mode:
        if uploaded_file:
            st.session_state.selected_model = "GLM-4V"
        elif len(prompt or "") > 800:
            st.session_state.selected_model = "Kimi"
        elif len(prompt or "") > 300:
            st.session_state.selected_model = "Doubao-Pro"
        else:
            st.session_state.selected_model = "DeepSeek"
    used_model = st.session_state.selected_model
    used_model_icon = MODEL_ICONS.get(
        used_model,
         "🤖",
    )
    with st.chat_message(
        "assistant",
        avatar=used_model_icon,
    ):
        st.caption(used_model)

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

            request_params = {
                "model": cfg["model"],
                "messages": api_messages,
                "stream": True,
            }

            if st.session_state.selected_model == "ChatGPT":
                request_params["max_completion_tokens"] = 2000
            else:
                request_params["temperature"] = 0.7
                request_params["max_tokens"] = 2000

            # ===== 自动判断并执行联网搜索 =====
            print(f"🧠 判断是否联网：{prompt}")

            if should_search(prompt):
                print("🌐 需要联网搜索")

                search_queries = plan_search(prompt)

                print(f"🧭 Search Planner 生成 {len(search_queries)} 条搜索词：")

                for index, query in enumerate(search_queries, start=1):
                    print(f"  {index}. {query}")

                

                search_results = []
                seen_urls = set()

                for index, query in enumerate(search_queries, start=1):
                    dated_query = get_search_query(query)

                    print(
                        f"🔎 执行第 {index}/{len(search_queries)} 次搜索："
                        f"{query}"
                    )

                    try:
                        current_results = search_web(
                            dated_query,
                            max_results=5,
                        )
                    except Exception as error:
                        print(f"⚠️ 第 {index} 次搜索失败：{error}")
                        current_results = []

                    print(f"   找到 {len(current_results)} 条结果")

                    for result in current_results:
                        url = (result.get("url") or "").strip()

                        if url:
                            normalized_url = url.rstrip("/").casefold()

                            if normalized_url in seen_urls:
                                continue

                            seen_urls.add(normalized_url)

                        search_results.append(result)

                    evaluation = evaluate_search_results(
                        user_prompt=prompt,
                        results=search_results,
                    )

                    print(
                        f"🧪 搜索评估："
                        f"{'资料足够' if evaluation['enough'] else '资料不足'}"
                    )
                    print(f"   原因：{evaluation['reason']}")

                    if evaluation["missing"]:
                        print(f"   仍缺少：{evaluation['missing']}")

                    if evaluation["enough"]:
                        print("✅ 已找到足够资料，提前停止搜索")
                        break

                    if index < len(search_queries):
                        print("🔁 当前资料不足，继续下一轮搜索")
                print(f"✅ 合并去重后共 {len(search_results)} 条结果")
                search_results = search_results[:10]

                print(f"📚 最终选取前 {len(search_results)} 条结果供模型分析")

                for result in search_results:
                    print(result.get("title", "无标题"))

                date_prompt = build_date_prompt()

                search_context = format_search_results(search_results)

                content = (
                    f"{date_prompt}\n\n"
                    "【联网搜索结果】\n\n"
                    f"{search_context}"
                )

                web_instruction = {
                    "role": "system",
                    "content": (
                        "你可以使用下面提供的联网搜索结果回答用户问题。\n"
                        "请严格遵守前面的日期校验规则。\n"
                        "不得把历史新闻当作最新新闻。\n"
                        "如果搜索结果日期不明确，请主动说明。\n"
                        "如果多个来源时间或数据冲突，请说明存在冲突。\n"
                        "除非来源明确提供带时区的更新时间，否则不要输出准确的当地当前时间。\n"
                        "天气观测时间必须标注为数据更新时间，不能当作当前系统时间。\n\n"
                        f"{content}"
                    ),
                }

                request_params["messages"] = [
                    web_instruction,
                    *api_messages,
                ]
              

            else:
                print("📚 不需要联网")

            stream = client.chat.completions.create(**request_params)

            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    full_response += chunk.choices[0].delta.content
                    placeholder.markdown(full_response + "▌")

            placeholder.markdown(full_response)


            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": full_response,
                    "model_name": used_model,
                    "model_icon": used_model_icon,
                }
            )
            save_message(
                st.session_state.current_session_id,
                "assistant",
                full_response,
                model_name=used_model,
                model_icon=used_model_icon,
            )
            # 每轮完整问答只保存一次最后活动时间
            save_last_activity(cookies)
            save_cookies(cookies)

            # 回答与数据库保存都完成后，再更新 URL
            st.query_params["chat"] = str(
                st.session_state.current_session_id
            )

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
                

            # 每次成功回答后刷新页面，让侧边栏用量立即更新
            st.rerun()

        except Exception as e:
            st.session_state.processing = False

            print("❌ 聊天调用完整异常：")
            traceback.print_exc()

            placeholder.error(f"调用失败: {str(e)}")


# ====================== Status ======================

