import base64
import json
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from dotenv import load_dotenv

import streamlit as st
import streamlit.components.v1 as components
from PIL import Image
from services.cookie_service import (
    create_cookie_manager,
    cookies_ready,
)
from supabase import create_client

from config import (
    SUPABASE_KEY,
    SUPABASE_SERVICE_KEY,
    SUPABASE_URL,
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
from services.task_classifier import classify_task
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
    restore_login_from_remember,
    save_remember_session,
    save_last_activity,
    load_last_activity,
    is_chat_activity_expired,
)
from services.search.search_router import (
    get_search_provider,
)

from services.search_router import should_search
from services.search_service import search_web, format_search_results
from services.date_service import (
    get_search_query,
    build_date_prompt,
)
from services.search_planner import plan_search
from services.search_evaluator import evaluate_search_results
from services.model_router import choose_auto_model
from services.model_config import (
    MODEL_CONFIGS,
    get_model_config,
    get_model_names,
)
from services.provider_service import (
    prepare_messages,
    stream_model_response,
)


from ui.chat_messages import render_chat_messages, render_user_content
from ui.sidebar import render_sidebar_placeholder, render_language_selector
from ui.brand_assets import (
    USER_AVATAR,
    apply_brand_css,
    model_avatar,
    render_brand_header,
    render_centered_text,
    render_sidebar_logo,
)
from i18n import initialize_language, t
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
    st.error(t("supabase_missing"))
    st.stop()

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
supabase_admin = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


# ====================== Cookie Bootstrap ======================

# EncryptedCookieManager 自带 ready() 初始化机制。
# 在浏览器 Cookie 尚未同步完成前停止本次执行，
# 组件准备好后 Streamlit 会自动重新运行。
cookies = create_cookie_manager()

if not cookies_ready(cookies):
    st.stop()

initialize_language(cookies)
apply_brand_css()

# ====================== Debug ======================
DEBUG = False
# ====================== Basic Utils ======================
def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()

# ====================== Device ID ======================
device_id = get_device_id()

if not device_id:
    device_id = st.session_state.get(
        "fallback_device_id"
    )

if not device_id:
    import uuid

    device_id = str(uuid.uuid4())
    st.session_state["fallback_device_id"] = device_id

# ====================== Model Config ======================
# Provider URLs, model IDs and API keys are centralized in
# services/model_config.py. Provider-specific request logic lives in
# services/provider_service.py.
model_options = MODEL_CONFIGS
MODEL_ICONS = {name: model_avatar(name) for name in get_model_names()}


def get_model_selector_options():
    return [t("auto_mode"), *get_model_names()]


MODEL_LABEL_TO_NAME = {
    model_name: model_name
    for model_name in get_model_names()
}

# ====================== Chat Database Functions ======================
def handle_model_selector_change():
    selected_label = st.session_state.model_selector

    if selected_label == t("auto_mode"):
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
            "last_seen": now_utc(),
            "plan": plan,
        },
        on_conflict="device_id",
    ).execute()

    enforce_device_limit(user.id, device_id, plan)



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


SESSION_DEFAULTS = {
    "user": None,
    "messages": [],
    "selected_model": "DeepSeek",
    "auto_mode": True,
    "auth_checked": False,
    "uploader_key": 0,
    "processing": False,
    "page": "chat",
}


for state_key, default_value in SESSION_DEFAULTS.items():
    if state_key not in st.session_state:
        # 对列表进行复制，避免以后扩展时共享可变对象。
        if isinstance(default_value, list):
            st.session_state[state_key] = default_value.copy()
        else:
            st.session_state[state_key] = default_value


if "model_selector" not in st.session_state:
    if st.session_state["auto_mode"]:
        st.session_state["model_selector"] = (
            t("auto_mode")
        )
    else:
        st.session_state["model_selector"] = st.session_state["selected_model"]


if "current_session_id" not in st.session_state:
    st.session_state["current_session_id"] = (
        get_chat_id_from_url()
    )


if "new_chat_mode" not in st.session_state:
    st.session_state["new_chat_mode"] = (
        st.session_state["current_session_id"] is None
    )


# ====================== Auto Login ======================

# Cookie 组件准备完成后，
# 每个新的 Streamlit 会话只检查一次长期登录。
if (
    st.session_state["user"] is None
    and not st.session_state["auth_checked"]
):
    restored_user = None

    try:
        restored_user = restore_login_from_remember(
            cookies,
            device_id,
        )

    except Exception as restore_error:
        print(
            "长期登录恢复失败:",
            restore_error,
        )

    # 无论成功或失败，本次 Streamlit 会话都已经完成认证检查。
    st.session_state["auth_checked"] = True

    if restored_user is not None:
        st.session_state["user"] = restored_user

        restored_chat_id = get_chat_id_from_url()

        try:
            last_activity = load_last_activity(
                cookies
            )

            activity_expired = (
                is_chat_activity_expired(
                    last_activity,
                    AUTO_NEW_CHAT_AFTER_MINUTES,
                )
            )

        except Exception as activity_error:
            print(
                "读取聊天活动时间失败:",
                activity_error,
            )
            activity_expired = False

        if activity_expired:
            # 无活动超过设定时间：
            # 保持登录，但进入一个新的空白聊天页面。
            st.session_state["current_session_id"] = None
            st.session_state["messages"] = []
            st.session_state["new_chat_mode"] = True
            st.session_state["processing"] = False

            remove_chat_id_from_url()

            print(
                "🆕 距离上次活动超过 "
                f"{AUTO_NEW_CHAT_AFTER_MINUTES} 分钟，"
                "进入新聊天页面"
            )

        else:
            # 活动时间未过期：
            # 恢复 URL 中指定的历史聊天。
            st.session_state["current_session_id"] = (
                restored_chat_id
            )
            st.session_state["messages"] = []
            st.session_state["new_chat_mode"] = (
                restored_chat_id is None
            )
            st.session_state["processing"] = False

            print(
                "✅ 长期登录恢复成功"
            )
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
        st.warning(t("history_load_failed", error=e))


# ====================== Login / Register Page ======================
if not st.session_state.user:
    render_brand_header(width=132)
    render_centered_text(t("sign_in_to_account"))

    tab1, tab2 = st.tabs([t("login_tab"), t("register_tab")])

    with tab1:
        email = st.text_input(t("email"), key="login_email")
        password = st.text_input(t("password"), type="password", key="login_pass")

        if st.button(
            t("sign_in"),
            use_container_width=True,
            key="login_btn",
        ):
            if not email or not password:
                st.error(t("missing_credentials"))

            else:
                # 第一层只负责 Supabase 身份认证。
                try:
                    res = supabase.auth.sign_in_with_password(
                        {
                            "email": email.strip(),
                            "password": password,
                        }
                    )

                except Exception as login_error:
                    st.error(t("sign_in_failed", error=login_error))

                else:
                    if not res or not res.user:
                        st.error(t("no_valid_user"))

                    else:
                        # 认证已经成功。下面的附加任务即使失败，
                        # 也不能再把页面显示为“登录失败”。
                        st.session_state["user"] = res.user
                        st.session_state["auth_checked"] = True
                        st.session_state["current_session_id"] = None
                        st.session_state["messages"] = []
                        st.session_state["new_chat_mode"] = True
                        st.session_state["processing"] = False


                        try:
                            save_remember_session(
                                res.user,
                                cookies,
                                device_id,
                            )
                        except Exception as remember_error:
                            print(
                                "长期登录记录保存失败，"
                                f"但不阻止本次登录: {remember_error}"
                            )

                        # 暂时保留设备数量管理，但它不再负责恢复登录。
                        if res.session:
                            try:
                                plan = get_user_plan(
                                    res.user.id
                                )

                                save_device_session(
                                    res.user,
                                    res.session,
                                    plan,
                                )

                            except Exception as device_error:
                                print(
                                    "设备记录更新失败，"
                                    f"但不阻止登录: {device_error}"
                                )

                        # 当前 Streamlit 会话已经登录成功，
                        # 直接进入主页面，不再强制刷新整个浏览器页面。
                        st.success(t("sign_in_success"))
                        st.rerun()

            

    with tab2:
        email_reg = st.text_input(t("register_email"), key="reg_email")
        password_reg = st.text_input(t("password_hint"), type="password", key="reg_pass")

        if st.button(t("sign_up"), use_container_width=True, key="reg_btn"):
            try:
                supabase.auth.sign_up(
                    {"email": email_reg, "password": password_reg}
                )
                st.success(t("sign_up_success"))
            except Exception as e:
                st.error(t("sign_up_failed", error=e))

    st.stop()


# ====================== Main Page ======================
user_email = getattr(
    st.session_state.user,
    "email",
    t("user_fallback"),
)

# 只有空白欢迎页显示居中的大 Logo；开始聊天后自动隐藏。
if not st.session_state.messages:
    render_brand_header(width=150)
    render_centered_text(
        t("welcome_back_plain", email=user_email)
    )

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
    render_sidebar_logo(width=68)
    render_language_selector(cookies)

    if st.button(
        t("sign_out"),
        use_container_width=True,
    ):
        # 阻止本次 rerun 再进行自动恢复。
        st.session_state.auth_checked = True

        # 撤销该设备的长期登录授权。
        try:
            clear_remember_session(
                cookies,
                device_id,
            )
        except Exception as remember_error:
            print(
                f"长期登录清理失败: {remember_error}"
            )

        # 删除设备管理记录。
        try:
            supabase_admin.table(
                "device_sessions"
            ).delete().eq(
                "device_id",
                device_id,
            ).execute()
        except Exception as device_error:
            print(
                f"删除设备记录失败: {device_error}"
            )

        # 注销当前 Supabase 会话。
        try:
            supabase.auth.sign_out()
        except Exception as signout_error:
            print(
                f"Supabase 退出失败: {signout_error}"
            )

        # 清理页面状态。
        st.session_state["user"] = None
        st.session_state["messages"] = []
        st.session_state["current_session_id"] = None
        st.session_state["new_chat_mode"] = True
        st.session_state["processing"] = False
        st.session_state["uploader_key"] += 1

        # 主动退出后，本次 Streamlit 会话不再尝试自动恢复。
        st.session_state["auth_checked"] = True
        remove_chat_id_from_url()
        st.rerun()
    # ====================== Plan and Daily Usage ======================

    with st.expander(t("my_account"), expanded=False):
        account = get_account_data(
            supabase_admin,
            st.session_state.user,
        )

        st.caption(t("email_caption"))
        st.write(account["email"])

        st.caption(t("current_plan"))

        if account["is_premium"]:
            st.success(t("premium"))
        else:
            st.info(t("free"))
        st.caption(t("today_usage"))

        if account["is_premium"]:
            st.markdown(t("unlimited_chat"))
            st.markdown(t("unlimited_images"))

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
                st.caption(t("usage_unavailable"))
        st.caption(t("subscription_status"))
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
                st.caption(t("premium_until"))
            else:
                st.caption(t("renewal_date"))

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
                st.warning(t("subscription_not_found"))

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
                        t("manage_subscription"),
                        portal_url,
                        use_container_width=True,
                    )
                else:
                    st.error(
                        t("portal_unavailable")
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
                t("upgrade_premium"),
                premium_checkout_url,
                use_container_width=True,
    )
    


    st.markdown("---")
    st.markdown("### " + t("chat_history"))

    if st.button(t("new_chat"), use_container_width=True):
        st.session_state.page = "chat"
        st.session_state.current_session_id = None
        st.session_state.messages = []
        st.session_state.new_chat_mode = True
        st.session_state.processing = False
        st.session_state.uploader_key += 1

        remove_chat_id_from_url()
        save_last_activity(cookies)
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

            st.session_state.uploader_key += 1
            st.session_state.processing = False
            st.rerun()

    if st.session_state.current_session_id:
        st.markdown("---")
        if st.button(t("delete_chat"), use_container_width=True):
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
if st.button(t("clear_chat")):
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
    t("model_label"),
    get_model_selector_options(),
    key="model_selector",
    on_change=handle_model_selector_change,
    label_visibility="collapsed",
)

submission = st.chat_input(
    t("ask_anything"),
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
        st.error(t("free_chat_exhausted"))
        st.link_button(
            t("upgrade_premium"),
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
        st.error(t("free_image_exhausted"))
        st.link_button(
            t("upgrade_premium"),
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
            {"type": "text", "text": prompt or t("describe_image")},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
        ]

    st.session_state.messages.append({"role": "user", "content": user_content})

    display_user_text = prompt if prompt else t("image_uploaded")
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
    

    with st.chat_message("user", avatar=USER_AVATAR):
        render_user_content(user_content)

    # 联网判断和模型调度都使用本地规则，不额外增加模型请求。
    needs_web_search = should_search(prompt)
    route_decision = None

    if st.session_state.auto_mode:
        route_decision = choose_auto_model(
            prompt,
            has_image=bool(uploaded_file),
            needs_search=needs_web_search,
        )
        st.session_state.selected_model = route_decision.model

    used_model = st.session_state.selected_model
    used_model_icon = MODEL_ICONS.get(
        used_model,
         "🤖",
    )
    with st.chat_message(
        "assistant",
        avatar=model_avatar(used_model),
    ):
        # 对用户只显示当前模型名称，不展示自动路由原因。
        st.caption(used_model)

        status_placeholder = st.empty()
        placeholder = st.empty()
        full_response = ""
        selected_model_name = st.session_state.selected_model
        

        task_info = classify_task(
            prompt,
            has_image=bool(uploaded_file),
        )

        search_provider = get_search_provider(
            selected_model_name,
            task_info.task_type,
        )
        

        if needs_web_search:
            status_placeholder.info(t("searching"))

        try:
            
            if (
                selected_model_name == "Grok"
                and task_info.task_type == "news"
                and search_provider is not None
            ):
                full_response = search_provider.search(
                    prompt
                )

                placeholder.markdown(full_response)

                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": full_response,
                        "model_name": selected_model_name,
                    }
                )
                
                st.session_state.processing = False
                st.stop()
            selected_config = get_model_config(selected_model_name)

            if not selected_config.api_key:
                placeholder.error(t("api_key_missing", model=selected_model_name))
                st.session_state.processing = False
                st.stop()

            # The unified provider layer handles message-format differences.
            api_messages = prepare_messages(
                selected_model_name,
                st.session_state.messages,
                history_limit=12,
            )

            selected_max_tokens = (
                route_decision.max_tokens
                if route_decision is not None
                else 1200
            )
            selected_temperature = (
                route_decision.temperature
                if route_decision is not None
                else 0.7
            )

            # ===== 自动判断并执行联网搜索 =====
            print(f"🧠 判断是否联网：{prompt}")

            if (
                needs_web_search
                and search_provider is not None
            ):
                
                print("🌐 需要联网搜索")
                if type(search_provider).__name__ == "GrokSearchProvider":

                    

                    full_response = search_provider.search(prompt)

                    placeholder.markdown(full_response)

                    st.session_state.messages.append(
                        {
                            "role": "assistant",
                            "content": full_response,
                            "model_name": selected_model_name,
                        }
                    )

                    st.session_state.processing = False
                    st.stop()

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

                api_messages = [
                    web_instruction,
                    *api_messages,
                ]


            else:
                print("📚 不需要联网")

            stream = stream_model_response(
                model_name=selected_model_name,
                messages=api_messages,
                max_tokens=selected_max_tokens,
                temperature=selected_temperature,
            )

            first_token_received = False

            for text_chunk in stream:
                if not first_token_received:
                    first_token_received = True
                    status_placeholder.empty()

                full_response += text_chunk
                placeholder.markdown(full_response + "▌")

            status_placeholder.empty()
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