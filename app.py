import base64
import json
import traceback
import uuid
import time
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
    can_use_chat,
    can_use_image,
    get_today_usage,
    increase_chat_usage,
    increase_image_usage,
    record_usage_event,
    can_start_request,
    FREE_CHAT_LIMIT,
    FREE_IMAGE_LIMIT,
    PREMIUM_DAILY_CHAT_LIMIT,
    PREMIUM_DAILY_IMAGE_LIMIT,
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
from services.search_planner import (
    plan_search_fast,
    resolve_search_query,
)
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
from services.freshness_service import judge_freshness

from services.native_search.native_search_factory import NativeSearchFactory

from uuid import uuid4


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
# Megor v2 Stable
# Streamlit + Supabase + Multi-model AI Chat
# ============================================================


# ====================== Page Config ======================
APP_DIR = Path(__file__).resolve().parent
MEGOR_ICON_PATH = APP_DIR / "static" / "megor-icon.png"

try:
    megor_page_icon = Image.open(MEGOR_ICON_PATH)
except Exception:
    megor_page_icon = "M"

st.set_page_config(
    page_title="Megor",
    page_icon=megor_page_icon,
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

        appTitle.setAttribute("content", "Megor");

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
    return [
        t("auto_mode"),
        *[
            MODEL_DISPLAY_NAMES.get(
                model_name,
                model_name
            )
            for model_name in sorted(get_model_names())
        ],
    ]


MODEL_DISPLAY_NAMES = {
    "ChatGPT": "ChatGPT-5.4 Mini",
    "Claude": "Claude-Sonnet 5",
    "DeepSeek": "DeepSeek-V4 Flash",
    "Doubao-Pro": "Doubao-Doubao Pro",
    "Gemini": "Gemini-3.6 Flash",
    "GLM": "ZhiPu-GLM 5.2 ",
    "Grok": "Grok-Grok 4.5",
    "Kimi": "Kimi-K2.5",
    "Qwen": "Qwen-3.6 Flash",
}
MODEL_LABEL_TO_NAME = {
    MODEL_DISPLAY_NAMES.get(model_name, model_name): model_name
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
    "https://megor-ai.lemonsqueezy.com/checkout/buy/6e539c0a-949d-4609-9678-a7f9b3d1bb3a"
)


def get_premium_checkout_url(user) -> str:
    """生成绑定当前 Megor AI 用户的 LemonSqueezy 付款链接。"""
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
    max_devices = 3 if plan == "premium" else 1

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

def clean_auth_fragment():
    """清理 Supabase 验证链接留下的 #error 参数，不刷新页面。"""
    st.html(
        """
        <script>
        const hash = window.location.hash;

        if (
            hash.includes("error=") ||
            hash.includes("error_code=") ||
            hash.includes("error_description=")
        ) {
            history.replaceState(
                null,
                "",
                window.location.pathname + window.location.search
            );
        }
        </script>
        """,
        unsafe_allow_javascript=True,
    )


clean_auth_fragment()

SESSION_DEFAULTS = {
    "user": None,
    "messages": [],
    "selected_model": "DeepSeek",
    "auto_mode": True,
    "auth_checked": False,
    "uploader_key": 0,
    "processing": False,
    "page": "chat",

    # 密码找回
    "password_recovery_mode": False,
    "recovery_access_token": None,
    "recovery_refresh_token": None,
}


for state_key, default_value in SESSION_DEFAULTS.items():
    if state_key not in st.session_state:
        # 对列表进行复制，避免以后扩展时共享可变对象。
        if isinstance(default_value, list):
            st.session_state[state_key] = default_value.copy()
        else:
            st.session_state[state_key] = default_value

# ====================== Password Recovery Link ======================

recovery_type = st.query_params.get("type")
recovery_token_hash = st.query_params.get("token_hash")

if (
    recovery_type == "recovery"
    and recovery_token_hash
    and not st.session_state["password_recovery_mode"]
):
    try:
        recovery_res = supabase.auth.verify_otp(
            {
                "token_hash": str(recovery_token_hash),
                "type": "recovery",
            }
        )

        if recovery_res and recovery_res.session:
            st.session_state["password_recovery_mode"] = True
            st.session_state["recovery_access_token"] = (
                recovery_res.session.access_token
            )
            st.session_state["recovery_refresh_token"] = (
                recovery_res.session.refresh_token
            )

            # 验证成功后清除敏感 token，保持地址栏干净
            params = st.query_params.to_dict()
            params.pop("token_hash", None)
            params.pop("type", None)
            st.query_params.from_dict(params)

    except Exception as recovery_error:
        st.error(
            f"Password recovery link is invalid or expired: "
            f"{recovery_error}"
        )
        st.stop()

# ====================== Set New Password ======================

if st.session_state["password_recovery_mode"]:

    try:
        supabase.auth.set_session(
            st.session_state["recovery_access_token"],
            st.session_state["recovery_refresh_token"],
        )
    except Exception as session_error:
        st.error(
            f"Password recovery session expired: {session_error}"
        )
        st.stop()

    render_brand_header(width=72)

    st.markdown("### 设置新密码")

    new_password = st.text_input(
        "新密码",
        type="password",
        key="new_password",
    )

    confirm_password = st.text_input(
        "确认新密码",
        type="password",
        key="confirm_new_password",
    )

    if st.button(
        "更新密码",
        key="update_password_btn",
    ):
        if not new_password or not confirm_password:
            st.error("请输入并确认新密码。")

        elif new_password != confirm_password:
            st.error("两次输入的密码不一致。")

        else:
            try:
                supabase.auth.update_user(
                    {
                        "password": new_password
                    }
                )

                # 修改完成，不继续保留 recovery session
                try:
                    supabase.auth.sign_out()
                except Exception:
                    pass

                st.session_state["password_recovery_mode"] = False
                st.session_state["recovery_access_token"] = None
                st.session_state["recovery_refresh_token"] = None
                st.session_state["user"] = None
                st.session_state["auth_checked"] = False

                st.success(
                    "密码已更新，请使用新密码重新登录。"
                )

            except Exception as update_error:
                st.error(
                    f"更新密码失败：{update_error}"
                )

    st.stop()


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
# 每个新的 Streamlit 会话检查长期登录。
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
            repr(restore_error),
        )

        # ⚠️ 临时恢复失败时，不立即标记认证检查完成
        # 允许下一次 rerun 再尝试恢复长期登录
        st.session_state["auth_checked"] = False

    else:
        # 只有 restore_login_from_remember 正常执行完成，
        # 才认为本次认证检查已经完成
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
    render_brand_header(width=72)

    st.markdown(
        f"""
    <div style="text-align:center;">

    <div style="
    font-size:29px;
    font-weight:600;
    margin-bottom:21px;
    ">
    {t("brand_tagline")}
    </div>

    <div style="
    font-size:18px;
    color:#666;
    ">
    {t("brand_description")}
    </div>

    </div>


    """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <h3 style="
        text-align:center;
        font-size:21px;
        font-weight:600;
        margin-top:30px;
        ">
        {t("login_title")}
        </h3>
        """,
        unsafe_allow_html=True,
    )

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

        st.markdown("---")

        if st.button(
            t("forgot_password"),
            key="forgot_password_btn",
        ):
            st.session_state["show_password_reset"] = True

        if st.session_state.get("show_password_reset", False):
            reset_email = st.text_input(
                t("reset_email"),
                key="reset_email",
            )

            if st.button(
                t("send_reset_email"),
                key="send_reset_email_btn",
            ):
                if not reset_email:
                    st.error(t("enter_reset_email"))
                else:
                    try:
                        supabase.auth.reset_password_for_email(
                            reset_email.strip(),
                            {
                                "redirect_to": "https://megor.ai"
                            },
                        )

                        st.success(t("reset_email_sent"))

                    except Exception as reset_error:
                        st.error(
                            f"Unable to send reset email: {reset_error}"
                        )

            

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
render_brand_header(width=68)

st.markdown(
    f"""
    **{t("brand_tagline")}**
    """
)

user_email = getattr(
    st.session_state.user,
    "email",
    t("user_fallback"),
)

if not st.session_state.messages:
    st.markdown(
        f"### {t('welcome_plain')}"
    )
    st.markdown(user_email)

# ====================== Sidebar ======================
# 用户从付款页返回 Megor 时，自动刷新一次页面，
# 以便重新读取最新的订阅状态。
components.html(
    """
    <script>
    (() => {
        const parentWindow = window.parent;
        const parentDocument = parentWindow.document;

        if (parentWindow.__megorVisibilityRefreshInstalled) {
            return;
        }

        parentWindow.__megorVisibilityRefreshInstalled = true;

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
            user_id = st.session_state.user.id
            today_usage = get_today_usage(
                supabase_admin,
                user_id,
            )
            st.markdown(
                t(
                    "chat_usage",
                    used=int(today_usage.get("chat_count", 0)),
                    limit=PREMIUM_DAILY_CHAT_LIMIT,
                )
            )

            st.markdown(
                t(
                    "image_usage",
                    used=int(today_usage.get("image_count", 0)),
                    limit=PREMIUM_DAILY_IMAGE_LIMIT,
                )
            )

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
                    f"💬 **{t('today_chat')}: "
                    f"{chat_count} / {FREE_CHAT_LIMIT}**"
                )
                st.progress(
                    min(
                        chat_count / FREE_CHAT_LIMIT,
                        1.0,
                    )
                )
                st.caption(
                    t("remaining_times").format(
                        count=chat_remaining
                    )
                )

                st.markdown(
                    f"🖼️ **{t('today_images')}: "
                    f"{image_count} / {FREE_IMAGE_LIMIT}**"
                )
                st.progress(
                    min(
                        image_count / FREE_IMAGE_LIMIT,
                        1.0,
                    )
                )
                st.caption(
                    t("remaining_times").format(
                        count=image_remaining
                    )
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


# ====================== Fixed Top Model Selector ======================

st.markdown(
    """
    <style>
    /* 顶部固定模型选择区 */
    .st-key-top_model_selector {
        position: fixed !important;
        top: 0.45rem;
        left: 50%;
        transform: translateX(-50%);
        width: 330px;
        z-index: 1000000;
    }

    /* 横排布局 */
    .st-key-top_model_selector > div {
        display: flex;
        align-items: center;
        gap: 8px;
    }

    /* “模型选择”文字 */
    .megor-model-label {
        font-size: 0.85rem;
        font-weight: 600;
        white-space: nowrap;
        margin: 0;
        padding: 0;
    }

    /* 下拉框 */
    .st-key-top_model_selector div[data-testid="stSelectbox"] {
        width: 180px !important;
        flex-shrink: 0;
    }
    /* 缩小模型选择框高度 */
    .st-key-top_model_selector div[data-baseweb="select"] > div {
        min-height: 34px !important;
        height: 34px !important;
    }

    /* 让框内文字和图标垂直居中 */
    .st-key-top_model_selector div[data-baseweb="select"] {
        min-height: 34px !important;
    }

    /* 手机端 */
    @media (max-width: 768px) {
        .st-key-top_model_selector {
            top: 0.30rem;
            width: auto !important;
        }

        .megor-model-label {
            font-size: 1rem;
            transform: translateX(138px) !important;
        }

        .st-key-top_model_selector div[data-testid="stSelectbox"] {
            width: 190px !important;
        }
        /* 手机端：模型文字和下拉框强制紧贴 */
        .st-key-top_model_selector div[data-testid="stHorizontalBlock"] {
            display: flex !important;
            flex-wrap: nowrap !important;
            flex-direction: row !important;
            justify-content: center !important;
            align-items: center !important;
            gap: 0 !important;
            width: auto !important;
        }

        /* 左侧 Model / 模型选择 */
        .st-key-top_model_selector div[data-testid="column"]:first-child {
            width: auto !important;
            min-width: 0 !important;
            flex: 0 0 auto !important;
            padding-right: 4px !important;
            margin-right: 0 !important;
        }

        /* 右侧下拉框 */
        .st-key-top_model_selector div[data-testid="column"]:last-child {
            width: 170px !important;
            min-width: 170px !important;
            flex: 0 0 170px !important;
            padding-left: 0 !important;
            margin-left: -8px !important;
        }

        /* 下拉框本体 */
                .st-key-top_model_selector div[data-testid="stSelectbox"] {
                    width: 170px !important;
                }
            }

            /* 手机端扩大左上角侧边栏展开按钮触控区域 */
            @media (max-width: 768px) {
                [data-testid="stSidebarCollapsedControl"] {
                    width: 48px !important;
                    height: 48px !important;
                    min-width: 48px !important;
                    min-height: 48px !important;
                }

                [data-testid="stSidebarCollapsedControl"] button {
                    width: 48px !important;
                    height: 48px !important;
                    min-width: 48px !important;
                    min-height: 48px !important;
                }
            }
            </style>
    """,
    unsafe_allow_html=True,
)

options = get_model_selector_options()

with st.container(
    key="top_model_selector",
):
    label_col, select_col = st.columns(
        [0.62, 2.38],
        gap="small",
        vertical_alignment="center",
    )

    with label_col:
        model_label = t("model_label")

        st.markdown(
            f'<div class="megor-model-label">{model_label}</div>',
            unsafe_allow_html=True,
        )

    with select_col:
        mode = st.selectbox(
            "",
            options,
            key="model_selector",
            label_visibility="collapsed",
        )

handle_model_selector_change()

# ====================== Display Messages ======================
render_chat_messages(
    st.session_state.messages
)



# ====================== Upload + Chat Input ======================



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
    perf_request_start = time.perf_counter()
    perf_last = perf_request_start

    print("\n" + "=" * 70)
    print("🚀 [PERF] NEW REQUEST")
    print(f"📝 [PERF] prompt={prompt[:80]!r}")

    user_id = st.session_state.user.id

    user_plan = (
        "premium"
        if account.get("is_premium")
        else "free"
    )
    
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

    print(
        f"⏱️ [PERF] initial_quota_check = "
        f"{time.perf_counter() - perf_last:.3f}s"
    )
    perf_last = time.perf_counter()

    st.session_state.processing = True

if st.session_state.processing:
    if not prompt:
        st.session_state.processing = False
        st.stop()

    # ==================================================
    # Response-first persistence
    #
    # 模型回答前不创建数据库会话、不写入消息。
    # 当前轮先只维护本地 session_state，模型完整回答成功后
    # 再统一创建会话、保存 user/assistant、更新标题与 URL。
    # ==================================================
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

    # 用户消息先只进入本地 session_state；
    # 数据库持久化延后到模型完整回答之后。
    with st.chat_message("user", avatar=USER_AVATAR):
        render_user_content(user_content)

    print(
        f"⏱️ [PERF] session+render = "
        f"{time.perf_counter() - perf_last:.3f}s"
    )
    perf_last = time.perf_counter()    

    # ==================================================
    # Self-deciding native search models
    #
    # ChatGPT / Grok / Gemini / Claude 在手动选择时，
    # 不再先调用 Qwen / Freshness AI 判断是否需要联网。
    # 是否真正执行原生搜索，由各自模型的 native search 流程自行决定。
    # Auto 模式暂时保持原有分类 / 路由逻辑，避免影响自动路由。
    # ==================================================
    SELF_DECIDING_SEARCH_MODELS = {
        "ChatGPT",
        "Grok",
        "Gemini",
        "Claude",
    }

    selected_model_before_routing = st.session_state.selected_model

    self_deciding_search_mode = (
        not st.session_state.auto_mode
        and selected_model_before_routing in SELF_DECIDING_SEARCH_MODELS
        and not bool(uploaded_file)
    )

    # 保留 ChatGPT 专用 unified Responses 标记，
    # 供后续 ChatGPT-specific 分支继续使用。
    chatgpt_unified_mode = (
        self_deciding_search_mode
        and selected_model_before_routing == "ChatGPT"
    )

    task_info = classify_task(
        prompt,
        has_image=bool(uploaded_file),
        skip_ai_freshness=self_deciding_search_mode,
    )

    print(
        f"⏱️ [PERF] classify_task = "
        f"{time.perf_counter() - perf_last:.3f}s"
    )
    perf_last = time.perf_counter()

    # ===== 最终联网判定 =====
    needs_web_search = task_info.need_search

    # 四个支持自主联网判断的模型，在手动选择时必须进入各自的
    # native search / unified 流程。这里的 True 仅表示“进入可联网流程”，
    # 不代表本轮一定实际联网；是否真正搜索由模型自身决定。
    if self_deciding_search_mode:
        needs_web_search = True

    # 图片本身不是联网理由。
    # 普通的看图、描述、识别、分析任务直接交给视觉模型。
    # 只有用户明确要求查询外部/实时信息时，才允许 Vision + Search。
    if task_info.task_type == "vision":
        prompt_lower = prompt.casefold()

        vision_search_keywords = (
            "搜索",
            "搜一下",
            "查一下",
            "查询",
            "联网",
            "最新",
            "现在",
            "目前",
            "当前",
            "今天",
            "最近",
            "实时",
            "新闻",
            "价格",
            "多少钱",
            "售价",
            "官网",
            "官方网站",
            "行情",
            "上市",
            "开放时间",
        )

        has_explicit_search_intent = any(
            keyword in prompt_lower
            for keyword in vision_search_keywords
        )

        if not has_explicit_search_intent:
            needs_web_search = False

    task_debug = task_info

    print(
        "DEBUG CLASSIFY:",
        task_debug.task_type,
        task_debug.need_search,
        task_debug.reason,
    )

    print(
        "DEBUG SHOULD_SEARCH:",
        needs_web_search,
    )
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

        # ==================================================
        # 当前回答区域定位点
        #
        # 位置放在模型名称下方。
        # 定位到这里时，上方可以看到用户刚发送的问题，
        # 下方可以看到当前模型及搜索 / 回答状态。
        # ==================================================
        st.html(
            '<div id="megor-response-start-anchor" style="height:1px;"></div>'
        )

        status_placeholder = st.empty()
        placeholder = st.empty()
        full_response = ""
        selected_model_name = st.session_state.selected_model

        current_user = st.session_state.get("user")
        
        current_user_id = (
            getattr(current_user, "id", None)
            or getattr(current_user, "user_id", None)
        )

        if not current_user_id and isinstance(current_user, dict):
            current_user_id = (
                current_user.get("id")
                or current_user.get("user_id")
            )

        current_plan = (
            "premium"
            if account.get("is_premium")
            else "free"
        )

        usage_request_id = str(uuid4())

        search_provider = get_search_provider(
            selected_model_name,
            task_info.task_type,
        )

        if needs_web_search and not chatgpt_unified_mode:
            status_placeholder.info(
                t("searching")
            )

        # ==================================================
        # 用户发送后立即定位到“本轮回答起点”
        #
        # 此时：
        # 1. 最新用户问题已经显示
        # 2. 当前模型名称已经显示
        # 3. 如果需要联网，“正在搜索”状态也已经显示
        #
        # 所以用户无需等待第一个 token。
        # ==================================================
        st.html(
            """
            <script>
            (() => {
                const scrollToResponseStart = () => {
                    const anchor = document.getElementById(
                        "megor-response-start-anchor"
                    );

                    if (!anchor) {
                        return;
                    }

                    anchor.scrollIntoView({
                        behavior: "auto",
                        block: "center"
                    });
                };

                scrollToResponseStart();
                setTimeout(scrollToResponseStart, 80);
                setTimeout(scrollToResponseStart, 200);
                setTimeout(scrollToResponseStart, 400);
            })();
            </script>
            """,
            unsafe_allow_javascript=True,
        )

        try:
            
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
                        # ===== 自动判断并执行联网搜索 =====
            print(f"🧠 判断是否联网：{prompt}")

            # 原生搜索如果已经生成完整答案，
            # 直接使用，不再进行第二次模型调用。
            native_direct_answer = None

            if needs_web_search:
                if chatgpt_unified_mode:
                    print("🧠 ChatGPT unified Responses mode")
                else:
                    print("🌐 需要联网搜索")

                # ==================================================
                # 先解析当前完整搜索问题
                # ==================================================
                native_perf_start = time.perf_counter()

                # ==================================================
                # 搜索 Query
                #
                # 不再预先调用额外 AI 改写搜索问题。
                # 当前用户原始问题直接交给 Native Search。
                #
                # 上下文型追问后续直接由 Native Search
                # 结合最近对话理解，避免再多一次模型请求。
                # ==================================================

                resolve_start = time.perf_counter()

                resolved_search_prompt = prompt.strip()

                print(
                    "⚡ SEARCH QUERY RESOLVER BYPASSED:",
                    repr(resolved_search_prompt),
                )

                print(
                    f"⏱️ [NATIVE PERF] resolve_search_query = "
                    f"{time.perf_counter() - resolve_start:.3f}s"
                )

                print(
                    "🧩 Resolved search prompt:",
                    resolved_search_prompt,
                )

                # ==================================================
                # 优先尝试当前模型自己的原生搜索
                # ==================================================
                native_search_used = False
                native_search_response = None

                if NativeSearchFactory.supports(selected_model_name):
                    print(
                        f"🧠 尝试 {selected_model_name} 原生搜索"
                    )

                    try:
                        if current_user_id:
                            native_preflight_start = time.perf_counter()

                            native_preflight = can_start_request(
                                supabase_admin,
                                user_id=str(current_user_id),
                                plan=str(current_plan),
                                model_key=selected_model_name,
                                request_type="native_search",
                            )

                            print(
                                f"⏱️ [NATIVE PERF] usage_preflight = "
                                f"{time.perf_counter() - native_preflight_start:.3f}s"
                            )

                            if not native_preflight["allowed"]:
                                print(
                                    "⛔ Native search blocked:",
                                    f"model={selected_model_name},",
                                    f"reason={native_preflight.get('reason')}",
                                )

                                if str(current_plan).lower() in {
                                    "pro",
                                    "premium",
                                    "paid",
                                }:
                                    st.warning(
                                        "Advanced real-time search is temporarily "
                                        "limited under fair-use controls."
                                    )
                                else:
                                    st.warning(
                                        t("advanced_search_requires_premium")
                                    )

                                st.stop()
                        factory_start = time.perf_counter()

                        native_search = NativeSearchFactory.create(
                            selected_model_name
                        )

                        print(
                            f"⏱️ [NATIVE PERF] factory_create = "
                            f"{time.perf_counter() - factory_start:.3f}s"
                        )

                        if native_search is not None:
                            native_api_start = time.perf_counter()

                        # ChatGPT 真正 Native Search 首个文本 delta 时间
                        native_first_delta_time = None


                        # ==================================================
                        # ChatGPT / Gemini / Grok / Claude
                        # 统一使用真正的 Native Search 流式输出
                        # ==================================================

                        if selected_model_name in SELF_DECIDING_SEARCH_MODELS:

                            openai_search_mode = (
                                "fast"
                                if task_info.task_type == "fast"
                                else "research"
                            )

                            print(
                                f"⚡ {selected_model_name} Native Search streaming"
                            )

                            native_search_response = None
                            native_stream_answer = ""

                            # ==================================================
                            # Native Search 上下文
                            #
                            # 只提供“紧邻当前问题的上一轮完整问答”，
                            # 不再把 api_messages 最近 4 条直接交给搜索。
                            #
                            # 当前 prompt 已经加入 st.session_state.messages，
                            # 所以通常：
                            #   -3 = 上一轮 user
                            #   -2 = 上一轮 assistant
                            #   -1 = 当前 user
                            # ==================================================

                            native_context_messages = []

                            session_messages = st.session_state.get(
                                "messages",
                                [],
                            )

                            if len(session_messages) >= 3:

                                previous_user = session_messages[-3]
                                previous_assistant = session_messages[-2]
                                current_message = session_messages[-1]

                                if (
                                    previous_user.get("role") == "user"
                                    and previous_assistant.get("role") == "assistant"
                                    and current_message.get("role") == "user"
                                ):
                                    native_context_messages = [
                                        previous_user,
                                        previous_assistant,
                                    ]

                            print(
                                "🧩 Native Search previous-turn context:",
                                [
                                    message.get("role")
                                    for message in native_context_messages
                                ],
                            )

                            stream_kwargs = {
                                "query": resolved_search_prompt,
                                "messages": native_context_messages,
                                "max_results": 8,
                            }

                            # ChatGPT 有自己的搜索模式参数
                            if selected_model_name == "ChatGPT":
                                stream_kwargs["search_mode"] = openai_search_mode

                            # Gemini / Grok / Claude 自己判断本轮是否真的需要联网。
                            # 即使模型判断无需搜索，也允许正常直接回答。
                            else:
                                stream_kwargs["allow_no_search"] = True

                            for event_kind, payload in native_search.stream_search(
                                **stream_kwargs
                            ):

                                # ==============================================
                                # OpenAI 真正返回的文本 delta
                                # ==============================================

                                if event_kind == "delta":

                                    delta = (
                                        payload
                                        if isinstance(payload, str)
                                        else str(payload or "")
                                    )

                                    if not delta:
                                        continue

                                    # ------------------------------------------
                                    # 第一个真实 token / delta
                                    # ------------------------------------------

                                    if native_first_delta_time is None:

                                        native_first_delta_time = (
                                            time.perf_counter()
                                        )

                                        status_placeholder.empty()

                                        print(
                                            f"⚡ [NATIVE STREAM PERF] "
                                            f"first_text_delta = "
                                            f"{native_first_delta_time - native_api_start:.3f}s"
                                        )

                                        print(
                                            f"🏁 [PERF] "
                                            f"TOTAL_TO_FIRST_STREAM_TOKEN = "
                                            f"{native_first_delta_time - perf_request_start:.3f}s"
                                        )

                                    native_stream_answer += delta

                                    # 使用 OpenAI 真实 delta 实时更新 UI
                                    full_response = native_stream_answer

                                    placeholder.markdown(
                                        full_response + "▌"
                                    )

                                    continue


                                # ==============================================
                                # 整个 Native Search 完成
                                # ==============================================

                                if event_kind == "complete":
                                    native_search_response = payload


                            # 理论上 stream_search 一定应该发送 complete
                            if native_search_response is None:
                                raise RuntimeError(
                                    "OpenAI native stream ended "
                                    "without a final NativeSearchResponse."
                                )


                            # 如果 streaming 搜索最终失败：
                            # 清掉可能已经显示出来的部分答案，
                            # 后面继续进入现有 Tavily Safety Net。
                            if not native_search_response.success:

                                placeholder.empty()
                                full_response = ""

                                print(
                                    "⚠️ OpenAI native streaming failed; "
                                    "partial streamed text cleared."
                                )


                        

                        # ==================================================
                        # Native Search 完整结束耗时
                        # ==================================================

                        native_api_elapsed = (
                            time.perf_counter() - native_api_start
                        )

                        print(
                            f"🌐 [NATIVE PERF] total_complete = "
                            f"{native_api_elapsed:.3f}s"
                        )

                        if native_search_response.success:
                            native_search_used = True

                            print(
                                f"✅ {selected_model_name} 原生搜索成功"
                            )

                            # ==================================================
                            # 记录原生搜索本身的真实成本
                            # ==================================================
                            native_usage = getattr(
                                native_search_response,
                                "usage",
                                None,
                            )

                            if native_usage:
                                native_usage_start = time.perf_counter()

                                try:
                                    current_user = st.session_state.get(
                                        "user"
                                    )

                                    current_user_id = (
                                        getattr(
                                            current_user,
                                            "id",
                                            None,
                                        )
                                        or getattr(
                                            current_user,
                                            "user_id",
                                            None,
                                        )
                                    )

                                    if (
                                        not current_user_id
                                        and isinstance(
                                            current_user,
                                            dict,
                                        )
                                    ):
                                        current_user_id = (
                                            current_user.get("id")
                                            or current_user.get(
                                                "user_id"
                                            )
                                        )

                                    if current_user_id:
                                        record_usage_event(
                                            supabase_admin,
                                            user_id=str(
                                                current_user_id
                                            ),
                                            model_key=(
                                                selected_model_name
                                            ),
                                            input_tokens=int(
                                                native_usage.get(
                                                    "input_tokens",
                                                    0,
                                                )
                                                or 0
                                            ),
                                            output_tokens=int(
                                                native_usage.get(
                                                    "output_tokens",
                                                    0,
                                                )
                                                or 0
                                            ),
                                            request_type=(
                                                "native_search"
                                            ),
                                            provider_actual_cost_usd=(
                                                native_usage.get(
                                                    "provider_cost_usd"
                                                )
                                            ),
                                            metadata={
                                                "source": (
                                                    "native_search"
                                                ),
                                                "server_side_tools": (
                                                    native_usage.get(
                                                        "server_side_tools",
                                                        0,
                                                    )
                                                ),
                                                "cost_in_usd_ticks": (
                                                    native_usage.get(
                                                        "cost_in_usd_ticks",
                                                        0,
                                                    )
                                                ),
                                            },
                                        )

                                        print(
                                            "💳 Native search usage recorded:",
                                            f"model={selected_model_name},",
                                            "cost_usd="
                                            f"{native_usage.get('provider_cost_usd')}",
                                        )

                                except Exception as usage_error:
                                    # 记账失败不能破坏搜索结果
                                    print(
                                        "⚠️ Native search usage "
                                        "recording failed:",
                                        repr(usage_error),
                                    )

                                print(
                                    f"💳 [NATIVE PERF] usage_recording = "
                                    f"{time.perf_counter() - native_usage_start:.3f}s"
                                )

                        else:
                            error_detail = (
                                native_search_response.error
                                or "Native search failed."
                            )

                            print(
                                f"⚠️ {selected_model_name} 原生搜索失败：",
                                error_detail,
                            )

                            if self_deciding_search_mode:
                                # 四个海外模型不再进入 Tavily，
                                # 也不进行第二次普通模型生成。
                                native_direct_answer = (
                                    "原生搜索暂时失败，请稍后重试。"
                                    if task_info.language == "zh"
                                    else "Native search temporarily failed. Please try again."
                                )

                    except Exception as error:
                        print(
                            f"⚠️ {selected_model_name} 原生搜索异常：",
                            error,
                        )

                        if self_deciding_search_mode:
                            native_direct_answer = (
                                "原生搜索暂时失败，请稍后重试。"
                                if task_info.language == "zh"
                                else "Native search temporarily failed. Please try again."
                            )

                # ==================================================
                # 原生搜索成功
                #
                # Native Search 本身已经完成：
                # 1. 联网搜索
                # 2. 阅读搜索结果
                # 3. 生成最终回答
                #
                # 因此直接使用 native answer，
                # 不再把它塞回模型进行第二次生成。
                # ==================================================
                if native_search_used and native_search_response is not None:

                    native_answer = (
                        native_search_response.answer
                        or ""
                    )

                    if not isinstance(native_answer, str):
                        native_answer = str(native_answer)

                    native_answer = native_answer.strip()

                    # ------------------------------
                    # 用户可见来源
                    #
                    # Native Search 的答案正文已经包含原生引用。
                    # 这里只补充“有真实标题”的来源，
                    # 不再生成无意义的 Source / 来源占位链接。
                    # ------------------------------
                    source_lines = []
                    seen_source_urls = set()

                    if native_search_response.results:
                        for result in native_search_response.results[:8]:

                            title = (
                                result.title
                                or ""
                            ).strip()

                            url = (
                                result.url
                                or ""
                            ).strip()

                            # 没有真实标题或 URL：
                            # 不额外显示，保留正文中的原生引用即可。
                            if not title or not url:
                                continue

                            normalized_url = (
                                url.rstrip("/").casefold()
                            )

                            if normalized_url in seen_source_urls:
                                continue

                            seen_source_urls.add(
                                normalized_url
                            )

                            source_lines.append(
                                f"- [{title}]({url})"
                            )

                    if source_lines:

                        sources_heading = (
                            "来源"
                            if task_info.language == "zh"
                            else "Sources"
                        )

                        native_answer = (
                            native_answer
                            + f"\n\n**{sources_heading}**\n"
                            + "\n".join(source_lines)
                        )
                    # 只有真正拿到回答才走直接返回。
                    # 如果原生搜索异常地没有 answer，
                    # 不在这里强行结束，后面仍可以继续正常流程。
                    if native_answer:
                        native_direct_answer = native_answer
                    

                        print(
                            f"⚡ {selected_model_name} "
                            "原生搜索答案直接返回，"
                            "跳过第二次模型生成"
                        )

                # ==================================================
                # 原生搜索失败 / 当前模型尚未接原生搜索
                # → Tavily Safety Net
                # ==================================================
                elif not self_deciding_search_mode:
                    
                    # Reuse the Qwen freshness decision already made by
                    # classify_task(). Do not call the judge a second time.
                    search_type = (
                        task_info.search_type
                        if task_info.need_search
                        else "none"
                    )

                    search_plan = plan_search_fast(
                        resolved_search_prompt,
                        search_type=search_type,
                    )

                    search_queries = search_plan.queries
                    preferred_domains = search_plan.preferred_domains

                    print(
                        f"🧭 Search Planner 生成 "
                        f"{len(search_queries)} 条搜索词："
                    )

                    for index, query in enumerate(
                        search_queries,
                        start=1,
                    ):
                        print(f"  {index}. {query}")

                    print(
                        "🏛️ Preferred domains:",
                        preferred_domains,
                    )

                    search_results = []
                    seen_urls = set()

                    # ==================================================
                    # CURRENT FACT
                    # 优先搜索第一方权威来源
                    # ==================================================
                    if (
                        search_type == "current_fact"
                        and preferred_domains
                    ):
                        print(
                            "🏛️ 当前事实查询："
                            "优先搜索第一方权威来源"
                        )

                        for index, query in enumerate(
                            search_queries,
                            start=1,
                        ):
                            print(
                                f"🔎 官方来源搜索 "
                                f"{index}/{len(search_queries)}："
                                f"{query}"
                            )

                            try:
                                current_results = search_web(
                                    query,
                                    max_results=5,
                                    search_type=search_type,
                                    include_domains=preferred_domains,
                                    search_depth="basic",
                                )

                            except Exception as error:
                                print(
                                    "⚠️ 官方来源搜索失败："
                                    f"{error}"
                                )
                                current_results = []

                            print(
                                f"   官方范围找到 "
                                f"{len(current_results)} 条结果"
                            )

                            for result in current_results:
                                url = (
                                    result.get("url")
                                    or ""
                                ).strip()

                                if url:
                                    normalized_url = (
                                        url
                                        .rstrip("/")
                                        .casefold()
                                    )

                                    if normalized_url in seen_urls:
                                        continue

                                    seen_urls.add(
                                        normalized_url
                                    )

                                search_results.append(
                                    result
                                )

                        evaluation = evaluate_search_results(
                            user_prompt=prompt,
                            results=search_results,
                            search_type=search_type,
                            preferred_domains=preferred_domains,
                        )

                        print(
                            "🏛️ 官方来源评估：",
                            evaluation,
                        )

                        # ==================================================
                        # 官方资料不足时，再进行普通互联网搜索
                        # ==================================================
                        if not evaluation.get(
                            "enough",
                            False,
                        ):
                            print(
                                "⚠️ 官方来源不足，"
                                "开始普通搜索补充资料"
                            )

                            for index, query in enumerate(
                                search_queries,
                                start=1,
                            ):
                                print(
                                    f"🌐 普通搜索 "
                                    f"{index}/{len(search_queries)}："
                                    f"{query}"
                                )

                                try:
                                    current_results = search_web(
                                        query,
                                        max_results=5,
                                        search_type=search_type,
                                    )

                                except Exception as error:
                                    print(
                                        "⚠️ 普通搜索失败："
                                        f"{error}"
                                    )
                                    current_results = []

                                print(
                                    f"   找到 "
                                    f"{len(current_results)} 条结果"
                                )

                                for result in current_results:
                                    url = (
                                        result.get("url")
                                        or ""
                                    ).strip()

                                    if url:
                                        normalized_url = (
                                            url
                                            .rstrip("/")
                                            .casefold()
                                        )

                                        if normalized_url in seen_urls:
                                            continue

                                        seen_urls.add(
                                            normalized_url
                                        )

                                    search_results.append(
                                        result
                                    )

                            evaluation = evaluate_search_results(
                                user_prompt=prompt,
                                results=search_results,
                                search_type=search_type,
                                preferred_domains=preferred_domains,
                            )

                    # ==================================================
                    # 其他联网类型
                    # recent_event / realtime_data / general_web
                    # ==================================================
                    else:
                        for index, query in enumerate(
                            search_queries,
                            start=1,
                        ):
                            print(
                                f"🔎 执行第 "
                                f"{index}/{len(search_queries)} "
                                f"次搜索：{query}"
                            )

                            try:
                                current_results = search_web(
                                    query,
                                    max_results=5,
                                    search_type=search_type,
                                    search_depth=(
                                        "basic"
                                        if search_type in {
                                            "current_fact",
                                            "realtime_data",
                                        }
                                        else "advanced"
                                    ),
                                )

                            except Exception as error:
                                print(
                                    f"⚠️ 第 {index} 次搜索失败："
                                    f"{error}"
                                )
                                current_results = []

                            print(
                                f"   找到 "
                                f"{len(current_results)} 条结果"
                            )

                            for result in current_results:
                                url = (
                                    result.get("url")
                                    or ""
                                ).strip()

                                if url:
                                    normalized_url = (
                                        url
                                        .rstrip("/")
                                        .casefold()
                                    )

                                    if normalized_url in seen_urls:
                                        continue

                                    seen_urls.add(
                                        normalized_url
                                    )

                                search_results.append(
                                    result
                                )

                            evaluation = evaluate_search_results(
                                user_prompt=prompt,
                                results=search_results,
                                search_type=search_type,
                            )

                            print(
                                f"🧪 搜索评估："
                                f"{'资料足够' if evaluation['enough'] else '资料不足'}"
                            )

                            print(
                                f"   原因："
                                f"{evaluation['reason']}"
                            )

                            if evaluation["missing"]:
                                print(
                                    f"   仍缺少："
                                    f"{evaluation['missing']}"
                                )

                            if evaluation["enough"]:
                                print(
                                    "✅ 已找到足够资料，"
                                    "提前停止搜索"
                                )
                                break

                            if index < len(search_queries):
                                print(
                                    "🔁 当前资料不足，"
                                    "继续下一轮搜索"
                                )

                        # ==================================================
                        # Fast Tavily safety retry
                        # current_fact / realtime_data first use BASIC.
                        # Only if the evaluator says evidence is insufficient
                        # do we pay for one ADVANCED retry.
                        # ==================================================
                        if (
                            search_type in {
                                "current_fact",
                                "realtime_data",
                            }
                            and not evaluation.get("enough", False)
                            and search_queries
                        ):
                            retry_query = search_queries[0]

                            print(
                                "⚠️ BASIC 搜索资料不足，"
                                "升级为 ADVANCED 再搜索 1 次"
                            )

                            try:
                                advanced_results = search_web(
                                    retry_query,
                                    max_results=5,
                                    search_type=search_type,
                                    search_depth="advanced",
                                )
                            except Exception as error:
                                print(
                                    "⚠️ ADVANCED 补充搜索失败："
                                    f"{error}"
                                )
                                advanced_results = []

                            print(
                                f"   ADVANCED 找到 "
                                f"{len(advanced_results)} 条结果"
                            )

                            for result in advanced_results:
                                url = (
                                    result.get("url")
                                    or ""
                                ).strip()

                                if url:
                                    normalized_url = (
                                        url
                                        .rstrip("/")
                                        .casefold()
                                    )

                                    if normalized_url in seen_urls:
                                        continue

                                    seen_urls.add(normalized_url)

                                search_results.append(result)

                            evaluation = evaluate_search_results(
                                user_prompt=prompt,
                                results=search_results,
                                search_type=search_type,
                            )

                            print(
                                "📊 ADVANCED 补充后评估：",
                                evaluation,
                            )

                    # ==================================================
                    # 最终搜索评估
                    # ==================================================
                    print(
                        "📊 搜索结果最终评估：",
                        evaluation,
                    )

                    print(
                        f"✅ 合并去重后共 "
                        f"{len(search_results)} 条结果"
                    )

                    search_results = search_results[:10]

                    print(
                        f"📚 最终选取前 "
                        f"{len(search_results)} 条结果供模型分析"
                    )

                    for result in search_results:
                        print(
                            result.get(
                                "title",
                                "无标题",
                            )
                        )

                    # ==================================================
                    # 搜索结果 → 模型上下文
                    # ==================================================
                    date_prompt = build_date_prompt()

                    search_context = format_search_results(
                        search_results
                    )

                    content = (
                        f"{date_prompt}\n\n"
                        "【联网搜索结果】\n\n"
                        f"{search_context}"
                    )

                    web_instruction = {
                        "role": "system",
                        "content": (
                            "你可以使用下面提供的联网搜索结果回答用户问题。\n\n"

                            "【联网回答最高优先级规则】\n"
                            "1. 对于会随时间变化的当前事实，"
                            "联网搜索结果优先于你的内部训练知识。\n"
                            "2. 不得使用内部记忆推翻可靠的最新搜索证据。\n"
                            "3. 如果你的内部知识与可靠搜索结果冲突，"
                            "必须采用可靠搜索结果。\n"
                            "4. 对现任政府领导人、公司高管、当前职位、"
                            "法律政策、产品版本、价格、市场数据等动态事实，"
                            "只能依据提供的搜索证据回答。\n"
                            "5. 如果搜索证据不足、来源互相矛盾或无法确认当前状态，"
                            "必须明确告诉用户“目前无法可靠确认”，不得猜测。\n"
                            "6. 优先采用官方机构、政府网站、公司官网"
                            "及其他第一方权威来源。\n"
                            "7. 不得因为某个旧来源排名靠前，"
                            "就把旧信息当成当前事实。\n\n"

                            "【日期与时效规则】\n"
                            "请严格遵守前面的日期校验规则。\n"
                            "不得把历史新闻当作最新新闻。\n"
                            "如果搜索结果日期不明确，请主动说明。\n"
                            "如果多个来源时间或数据冲突，请说明存在冲突。\n"
                            "除非来源明确提供带时区的更新时间，"
                            "否则不要输出准确的当地当前时间。\n"
                            "天气观测时间必须标注为数据更新时间，"
                            "不能当作当前系统时间。\n\n"

                            f"{content}"
                        ),
                    }

                    api_messages = [
                        web_instruction,
                        *api_messages,
                    ]

            else:
                print("📚 不需要联网")

            

            # ==================================================
            # 原生搜索已经生成最终答案
            # → 直接显示
            # ==================================================

            if native_direct_answer is not None:

                status_placeholder.empty()

                # ==============================================
                # Streaming 已经实时显示正文。
                # 这里仅用最终完整答案刷新一次，
                # 主要用于补齐最终 citations / sources。
                # ==============================================

                full_response = native_direct_answer

                placeholder.markdown(
                    full_response
                )

                native_complete_time = (
                    time.perf_counter()
                )

                print(
                    "⚡ [PERF] SECOND_PROVIDER_CALL = SKIPPED"
                )

                # 四个海外模型真正 Native Streaming：
                # 首字时间已经在第一个 delta 时打印，
                # 这里不再错误地把“全文完成时间”叫 First Token。
                if (
                    selected_model_name in SELF_DECIDING_SEARCH_MODELS
                    and native_first_delta_time is not None
                ):
                    print(
                        f"🏁 [NATIVE STREAM PERF] "
                        f"total_complete = "
                        f"{native_complete_time - native_api_start:.3f}s"
                    )

                    print(
                        f"🏁 [PERF] "
                        f"TOTAL_NATIVE_COMPLETE = "
                        f"{native_complete_time - perf_request_start:.3f}s"
                    )

                else:

                    # 其他目前尚未支持 Native Streaming 的模型
                    print(
                        f"🏁 [PERF] TOTAL_TO_FIRST_TOKEN = "
                        f"{native_complete_time - perf_request_start:.3f}s"
                    )

                print("=" * 70)


            # ==================================================
            # 非原生搜索直出
            # 包括：
            # 1. 普通非联网回答
            # 2. Tavily Safety Net
            #
            # 这些仍然需要模型生成最终答案。
            # ==================================================

            else:

                # ==================================================
                # Usage preflight
                # ==================================================

                preflight = None

                print(
                    f"⏱️ [PERF] routing+search_before_preflight = "
                    f"{time.perf_counter() - perf_last:.3f}s"
                )
                perf_last = time.perf_counter()

                if current_user_id:
                    preflight = can_start_request(
                        supabase_admin,
                        user_id=str(current_user_id),
                        plan=str(current_plan),
                        model_key=selected_model_name,
                        request_type="text",
                    )

                    if not preflight["allowed"]:
                        reason = preflight.get("reason")

                        if str(current_plan).lower() in {
                            "pro",
                            "premium",
                            "paid",
                        }:
                            st.warning(
                                t("pro_fair_use_limit")
                            )

                        elif reason in {
                            "daily_credit_exhausted",
                            "monthly_credit_exhausted",
                        }:
                            st.warning(
                                t("free_quota_exhausted")
                            )

                        else:
                            st.warning(
                                t(
                                    "model_quota_insufficient"
                                ).format(
                                    model=selected_model_name
                                )
                            )

                        st.stop()

                    usage_max_output = (
                        preflight
                        .get("usage_status", {})
                        .get("max_output_tokens")
                    )

                    if usage_max_output is not None:
                        selected_max_tokens = min(
                            int(selected_max_tokens),
                            int(usage_max_output),
                        )

                    cooldown_seconds = int(
                        preflight
                        .get("usage_status", {})
                        .get("cooldown_seconds")
                        or 0
                    )

                    if cooldown_seconds > 0:
                        with st.spinner(
                            t("fair_use_processing")
                        ):
                            time.sleep(
                                cooldown_seconds
                            )

                print(
                    f"⏱️ [PERF] final_usage_preflight = "
                    f"{time.perf_counter() - perf_last:.3f}s"
                )

                perf_before_provider = (
                    time.perf_counter()
                )

                print(
                    f"⏱️ [PERF] BEFORE PROVIDER TOTAL = "
                    f"{perf_before_provider - perf_request_start:.3f}s"
                )

                # ==================================================
                # 真正的模型生成
                # ==================================================

                stream = stream_model_response(
                    model_name=selected_model_name,
                    messages=api_messages,
                    max_tokens=selected_max_tokens,
                    temperature=selected_temperature,
                    supabase_admin=supabase_admin,
                    user_id=(
                        str(current_user_id)
                        if current_user_id
                        else None
                    ),
                    request_type="text",
                )

                # 当前模型回答的位置锚点
                st.html(
                    '<div id="megor-current-answer-anchor" '
                    'style="height:1px;"></div>'
                )

                first_token_received = False

                for text_chunk in stream:

                    if not first_token_received:
                        first_token_received = True

                        first_token_time = (
                            time.perf_counter()
                        )

                        print(
                            f"🤖 [PERF] provider_to_first_token = "
                            f"{first_token_time - perf_before_provider:.3f}s"
                        )

                        print(
                            f"🏁 [PERF] TOTAL_TO_FIRST_TOKEN = "
                            f"{first_token_time - perf_request_start:.3f}s"
                        )

                        print("=" * 70)

                        status_placeholder.empty()

                        # 第一个 token 出现时，
                        # 把当前模型回答带入可视区域。
                        st.html(
                            """
                            <script>
                            (() => {
                                const scrollToAnswer = () => {
                                    const anchor =
                                        document.getElementById(
                                            "megor-current-answer-anchor"
                                        );

                                    if (!anchor) {
                                        return;
                                    }

                                    anchor.scrollIntoView({
                                        behavior: "auto",
                                        block: "start"
                                    });
                                };

                                scrollToAnswer();
                                setTimeout(
                                    scrollToAnswer,
                                    80
                                );
                                setTimeout(
                                    scrollToAnswer,
                                    200
                                );
                            })();
                            </script>
                            """,
                            unsafe_allow_javascript=True,
                        )

                    full_response += text_chunk

                    placeholder.markdown(
                        full_response + "▌"
                    )

                status_placeholder.empty()
                placeholder.markdown(
                    full_response
                )


            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": full_response,
                    "model_name": used_model,
                    "model_icon": used_model_icon,
                }
            )

            # ==================================================
            # 模型完整回答成功后，再统一执行持久化。
            # ==================================================
            try:
                if st.session_state.current_session_id is None:
                    new_session_id = create_new_chat(
                        st.session_state.user.id
                    )
                    st.session_state.current_session_id = new_session_id
                    st.session_state.new_chat_mode = False

                save_message(
                    st.session_state.current_session_id,
                    "user",
                    content_to_save,
                )

                update_chat_title_if_needed(
                    st.session_state.current_session_id,
                    prompt,
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

            except Exception as persistence_error:
                print(
                    "Post-response persistence failed:",
                    repr(persistence_error),
                )

            # 只有模型成功返回后才扣除额度
            try:
                user_id = st.session_state.user.id
                user_plan = get_user_plan(user_id) or "free"
                user_plan = str(user_plan).lower()

                increase_chat_usage(
                    supabase_admin,
                    user_id,
                )

                if uploaded_file:
                    increase_image_usage(
                        supabase_admin,
                        user_id,
                    )

            except Exception as usage_error:
                print(
                    f"Usage update failed: {usage_error}"
                )
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