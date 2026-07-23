import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any, Optional

from database import supabase_admin



def now_utc() -> str:
    """返回当前 UTC 时间的 ISO 格式字符串。"""
    return datetime.now(timezone.utc).isoformat()


def generate_remember_token() -> str:
    """生成用于记住登录状态的随机 Token。"""
    return secrets.token_urlsafe(48)


def hash_remember_token(token: str) -> str:
    """对 Remember Token 进行 SHA-256 哈希。"""
    return hashlib.sha256(token.encode()).hexdigest()


def save_remember_session(
    user,
    cookies,
    device_id,
    save: bool = True,
):
    """保存长期登录记录，并将 Remember Token 写入 Cookie。"""

    token = generate_remember_token()
    token_hash = hash_remember_token(token)

    expires_at = (
        datetime.now(timezone.utc) + timedelta(days=30)
    ).isoformat()

    # 删除当前用户旧的长期登录记录
    supabase_admin.table("remember_sessions").delete().eq(
        "user_id",
        user.id,
    ).execute()

    # 保存新的长期登录记录
    supabase_admin.table("remember_sessions").insert(
        {
            "user_id": user.id,
            "email": user.email,
            "token_hash": token_hash,
            "device_id": device_id,
            "expires_at": expires_at,
        }
    ).execute()

    # 保存新的 Remember Token
    cookies["remember_token"] = token

    # 清除旧 Supabase Token，避免 Already Used 冲突
    cookies["remember_token"] = token
    if save:
        cookies.save()


def restore_login_from_remember(
    cookies: Any,
    device_id: str,
) -> Optional[SimpleNamespace]:
    """根据设备上的长期登录记录恢复用户。"""

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

        # 更新最近使用时间
        supabase_admin.table("remember_sessions").update(
            {
                "last_seen": now_utc(),
            }
        ).eq(
            "id",
            saved["id"],
        ).execute()

        return SimpleNamespace(
            id=saved.get("user_id"),
            email=saved.get("email") or "用户",
        )

    except Exception as error:
        print(f"Remember restore failed: {error}")
        return None


def clear_remember_session(cookies: Any) -> None:
    """删除长期登录记录，并清空相关 Cookie。"""

    token = cookies.get("remember_token")

    if token:
        token_hash = hash_remember_token(token)

        supabase_admin.table("remember_sessions").delete().eq(
            "token_hash",
            token_hash,
        ).execute()

    cookies["remember_token"] = ""
    cookies["access_token"] = ""
    cookies["refresh_token"] = ""
    cookies["login_saved_at"] = ""

    cookies.save()

from datetime import datetime, timezone


def save_last_activity(cookies):
    """更新最后活动时间，但不在这里调用 cookies.save()。"""
    cookies["last_activity"] = datetime.now(timezone.utc).isoformat()


def load_last_activity(cookies):
    value = cookies.get("last_activity")

    if not value:
        return None

    try:
        return datetime.fromisoformat(value)
    except:
        return None

def is_chat_activity_expired(
    last_activity,
    timeout_minutes: int,
) -> bool:
    """
    判断用户是否超过指定分钟数没有活动。

    没有历史活动时间时暂不判定过期，
    避免升级后所有老用户突然丢失当前页面。
    """
    if last_activity is None:
        return False

    now_utc = datetime.now(timezone.utc)
    elapsed_seconds = (
        now_utc - last_activity
    ).total_seconds()

    return elapsed_seconds > timeout_minutes * 60

def save_auth_cookies(
    cookies,
    session,
    now_utc,
    save: bool = True,
):
    if not session:
        return

    cookies["access_token"] = session.access_token
    cookies["refresh_token"] = session.refresh_token
    cookies["login_saved_at"] = now_utc()

    if save:
        cookies.save()

def restore_login_from_cookies(
    cookies,
    supabase,
    now_utc,
):
    access_token = cookies.get("access_token")
    refresh_token = cookies.get("refresh_token")

    print("Access exists:", bool(access_token))
    print("Refresh exists:", bool(refresh_token))

    if not refresh_token:
        return None

    try:
        if access_token:
            result = supabase.auth.set_session(
                access_token,
                refresh_token,
            )
        else:
            result = supabase.auth.refresh_session(
                refresh_token,
            )

        if result and result.user:
            if result.session:
                save_auth_cookies(
                    cookies,
                    result.session,
                    now_utc,
                )

            return result.user

    except Exception as error:
        print(f"Cookie restore failed: {error}")

        cookies["access_token"] = ""
        cookies["refresh_token"] = ""
        cookies.save()

    return None