import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any, Optional

from database import supabase_admin
from services.cookie_service import delete_cookie, get_cookie, persist_cookies, set_cookie

REMEMBER_COOKIE = "remember_token"
LAST_ACTIVITY_COOKIE = "last_activity"
REMEMBER_DAYS = 30


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def generate_remember_token() -> str:
    return secrets.token_urlsafe(48)


def hash_remember_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def save_remember_session(user, cookies, device_id: str) -> None:
    token = generate_remember_token()
    token_hash = hash_remember_token(token)
    expires_at = (datetime.now(timezone.utc) + timedelta(days=REMEMBER_DAYS)).isoformat()

    # device_id 只用于设备管理，不再作为恢复登录的必要条件。
    # Safari/iOS 会限制组件 iframe 内的 localStorage/cookie，device_id 可能变化。
    if device_id:
        (supabase_admin.table("remember_sessions").delete()
         .eq("device_id", device_id).execute())

    (supabase_admin.table("remember_sessions").insert({
        "user_id": user.id,
        "email": user.email,
        "token_hash": token_hash,
        "device_id": device_id or None,
        "expires_at": expires_at,
        "last_seen": now_utc(),
    }).execute())

    set_cookie(cookies, REMEMBER_COOKIE, token)
    set_cookie(cookies, LAST_ACTIVITY_COOKIE, now_utc())
    persist_cookies(cookies)
    print("✅ 长期登录 Cookie 已提交保存")


def restore_login_from_remember(cookies, device_id: str) -> Optional[SimpleNamespace]:
    """仅凭不可猜测的 remember_token 恢复登录，不依赖 Safari 中不稳定的 device_id。"""
    token = get_cookie(cookies, REMEMBER_COOKIE)
    if not token:
        print("ℹ️ 未读取到 remember_token")
        return None

    token_hash = hash_remember_token(token)
    try:
        result = (supabase_admin.table("remember_sessions").select("*")
                  .eq("token_hash", token_hash)
                  .gt("expires_at", now_utc()).limit(1).execute())
        if not result.data:
            print("ℹ️ remember_token 无匹配记录或已过期")
            return None

        saved = result.data[0]
        (supabase_admin.table("remember_sessions").update({
            "last_seen": now_utc(),
            # 新 device_id 可用于后续设备列表更新，但不影响认证。
            "device_id": device_id or saved.get("device_id"),
        }).eq("id", saved["id"]).execute())

        return SimpleNamespace(id=saved["user_id"], email=saved.get("email", "用户"))
    except Exception as error:
        print(f"长期登录恢复失败：{error}")
        return None


def clear_remember_session(cookies: Any, device_id: str) -> None:
    """按当前浏览器中的 token 精确撤销，避免 iPhone device_id 变化导致退出不彻底。"""
    token = get_cookie(cookies, REMEMBER_COOKIE)
    if token:
        try:
            token_hash = hash_remember_token(token)
            (supabase_admin.table("remember_sessions").delete()
             .eq("token_hash", token_hash).execute())
        except Exception as error:
            print(f"删除 remember_sessions 失败：{error}")

    delete_cookie(cookies, REMEMBER_COOKIE)
    delete_cookie(cookies, LAST_ACTIVITY_COOKIE)
    persist_cookies(cookies)


def save_last_activity(cookies: Any) -> None:
    try:
        set_cookie(cookies, LAST_ACTIVITY_COOKIE, now_utc())
        persist_cookies(cookies)
    except Exception as error:
        print(f"最后活动时间保存失败：{error}")


def load_last_activity(cookies: Any) -> Optional[datetime]:
    value = get_cookie(cookies, LAST_ACTIVITY_COOKIE)
    if not value:
        return None
    try:
        result = datetime.fromisoformat(value)
        if result.tzinfo is None:
            result = result.replace(tzinfo=timezone.utc)
        return result.astimezone(timezone.utc)
    except (TypeError, ValueError):
        try:
            delete_cookie(cookies, LAST_ACTIVITY_COOKIE)
            persist_cookies(cookies)
        except Exception as error:
            print(f"清理无效活动 Cookie 失败：{error}")
        return None


def is_chat_activity_expired(last_activity: Optional[datetime], timeout_minutes: int) -> bool:
    if last_activity is None:
        return False
    elapsed_seconds = (datetime.now(timezone.utc) - last_activity).total_seconds()
    return elapsed_seconds > max(int(timeout_minutes), 1) * 60
