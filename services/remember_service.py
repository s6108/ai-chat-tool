import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any, Optional

from database import supabase_admin
from services.cookie_service import (
    delete_cookie,
    get_cookie,
    persist_cookies,
    set_cookie,
)


REMEMBER_COOKIE = "remember_token"
LAST_ACTIVITY_COOKIE = "last_activity"
REMEMBER_DAYS = 30


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def generate_remember_token() -> str:
    return secrets.token_urlsafe(48)


def hash_remember_token(token: str) -> str:
    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()


def save_remember_session(
    user,
    cookies,
    device_id: str,
) -> None:
    """
    创建长期登录记录。

    remember_token 和 last_activity 先一起写入内存，
    最后只调用一次 persist_cookies()。
    """
    token = generate_remember_token()
    token_hash = hash_remember_token(token)

    expires_at = (
        datetime.now(timezone.utc)
        + timedelta(days=REMEMBER_DAYS)
    ).isoformat()

    # 当前设备只保留一条有效长期登录记录。
    (
        supabase_admin
        .table("remember_sessions")
        .delete()
        .eq("device_id", device_id)
        .execute()
    )

    (
        supabase_admin
        .table("remember_sessions")
        .insert(
            {
                "user_id": user.id,
                "email": user.email,
                "token_hash": token_hash,
                "device_id": device_id,
                "expires_at": expires_at,
                "last_seen": now_utc(),
            }
        )
        .execute()
    )

    # 这里只修改 Cookie 内存状态。
    set_cookie(
        cookies,
        REMEMBER_COOKIE,
        token,
    )

    set_cookie(
        cookies,
        LAST_ACTIVITY_COOKIE,
        now_utc(),
    )

    persist_result = persist_cookies(cookies)

    print(
        "[REMEMBER SAVE] Cookie 保存调用完成，"
        f"persist_result={persist_result}"
    )

    print(
        "[REMEMBER SAVE] remember_token 前8位："
        f"{token[:8]}"
    )


def restore_login_from_remember(
    cookies,
    device_id: str,
) -> Optional[SimpleNamespace]:
    print(
        "[REMEMBER RESTORE] 开始恢复长期登录，"
        f"device_id={device_id}"
    )

    token = get_cookie(
        cookies,
        REMEMBER_COOKIE,
    )

    if token:
        print(
            "[REMEMBER RESTORE] 已读取 remember_token，"
            f"前8位={token[:8]}"
        )
    else:
        print(
            "[REMEMBER RESTORE] remember_token=None"
        )

    if not token:
        return None

    token_hash = hash_remember_token(token)

    try:
        result = (
            supabase_admin
            .table("remember_sessions")
            .select("*")
            .eq("device_id", device_id)
            .eq("token_hash", token_hash)
            .gt("expires_at", now_utc())
            .limit(1)
            .execute()
        )

        print(
            "[REMEMBER RESTORE] 数据库匹配记录数："
            f"{len(result.data or [])}"
        )

        if not result.data:
            print(
                "[REMEMBER RESTORE] Cookie 存在，"
                "但数据库没有匹配记录"
            )
            return None

        saved = result.data[0]

        print(
            "[REMEMBER RESTORE] 长期登录恢复成功，"
            f"email={saved.get('email')}"
        )

        return SimpleNamespace(
            id=saved["user_id"],
            email=saved.get("email", "用户"),
        )

    except Exception as error:
        print(
            "[REMEMBER RESTORE] 恢复异常："
            f"{error}"
        )
        return None


def clear_remember_session(
    cookies: Any,
    device_id: str,
) -> None:
    """撤销当前设备长期登录并删除 Cookie。"""
    if device_id:
        try:
            (
                supabase_admin
                .table("remember_sessions")
                .delete()
                .eq("device_id", device_id)
                .execute()
            )
        except Exception as error:
            print(
                f"删除 remember_sessions 失败：{error}"
            )

    delete_cookie(
        cookies,
        REMEMBER_COOKIE,
    )
    delete_cookie(
        cookies,
        LAST_ACTIVITY_COOKIE,
    )

    # 两个删除操作完成后只保存一次。
    persist_cookies(cookies)


def save_last_activity(
    cookies: Any,
) -> None:
    """保存最后一次有效聊天活动时间。"""
    try:
        set_cookie(
            cookies,
            LAST_ACTIVITY_COOKIE,
            now_utc(),
        )

        persist_cookies(cookies)

    except Exception as error:
        print(f"最后活动时间保存失败：{error}")


def load_last_activity(
    cookies: Any,
) -> Optional[datetime]:
    value = get_cookie(
        cookies,
        LAST_ACTIVITY_COOKIE,
    )

    if not value:
        return None

    try:
        result = datetime.fromisoformat(value)

        if result.tzinfo is None:
            result = result.replace(
                tzinfo=timezone.utc
            )

        return result.astimezone(timezone.utc)

    except (TypeError, ValueError):
        # Cookie 内容损坏时删除一次。
        try:
            delete_cookie(
                cookies,
                LAST_ACTIVITY_COOKIE,
            )
            persist_cookies(cookies)
        except Exception as error:
            print(
                f"清理无效活动 Cookie 失败：{error}"
            )

        return None


def is_chat_activity_expired(
    last_activity: Optional[datetime],
    timeout_minutes: int,
) -> bool:
    if last_activity is None:
        return False

    elapsed_seconds = (
        datetime.now(timezone.utc)
        - last_activity
    ).total_seconds()

    return (
        elapsed_seconds
        > max(int(timeout_minutes), 1) * 60
    )