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


def restore_login_from_remember(
    cookies,
    device_id: str
) -> Optional[SimpleNamespace]:
    """仅凭 remember_token 恢复登录，不依赖 Safari 中不稳定的 device_id。"""

    token = get_cookie(cookies, REMEMBER_COOKIE)

    if not token:
        print("ℹ️ 未读取到 remember_token")
        return None

    token_hash = hash_remember_token(token)

    # ==================================================
    # 1. 查询 remember_session
    #    如果这里发生异常，必须继续抛给外层，
    #    不能把临时网络/数据库错误当成“未登录”
    # ==================================================
    try:
        result = (
            supabase_admin
            .table("remember_sessions")
            .select("*")
            .eq("token_hash", token_hash)
            .gt("expires_at", now_utc())
            .limit(1)
            .execute()
        )

    except Exception as error:
        print(
            "❌ 查询 remember_session 失败：",
            repr(error),
        )

        # 关键：
        # 让外层知道这是“恢复过程异常”，
        # 而不是“remember_token 不存在”
        raise

    # ==================================================
    # 2. 查询成功，但确实没有有效记录
    # ==================================================
    if not result.data:
        print("ℹ️ remember_token 无匹配记录或已过期")
        return None

    saved = result.data[0]

    # ==================================================
    # 3. 到这里已经可以确认用户身份。
    #    为减少 App 启动关键路径中的数据库写入：
    #    - device_id 发生变化时才立即同步；
    #    - device_id 未变化时，last_seen 仅在距离上次更新 >= 24 小时后同步。
    #    这不会改变 remember_token 的身份验证逻辑。
    # ==================================================
    should_update_session = False

    saved_device_id = saved.get("device_id")
    current_device_id = device_id or saved_device_id

    if current_device_id and current_device_id != saved_device_id:
        should_update_session = True
    else:
        last_seen_raw = saved.get("last_seen")
        if not last_seen_raw:
            should_update_session = True
        else:
            try:
                last_seen = datetime.fromisoformat(
                    str(last_seen_raw).replace("Z", "+00:00")
                )
                if last_seen.tzinfo is None:
                    last_seen = last_seen.replace(tzinfo=timezone.utc)

                should_update_session = (
                    datetime.now(timezone.utc) - last_seen
                    >= timedelta(hours=24)
                )
            except (TypeError, ValueError):
                # 无法解析旧记录时允许修复一次，不影响登录结果。
                should_update_session = True

    if should_update_session:
        try:
            (
                supabase_admin
                .table("remember_sessions")
                .update({
                    "last_seen": now_utc(),
                    "device_id": current_device_id,
                })
                .eq("id", saved["id"])
                .execute()
            )

        except Exception as error:
            print(
                "⚠️ remember_session 状态更新失败，"
                "但不影响登录：",
                repr(error),
            )

    # ==================================================
    # 4. 返回已恢复用户
    # ==================================================
    print(
        "✅ remember_token 验证成功：",
        saved["user_id"],
    )

    return SimpleNamespace(
        id=saved["user_id"],
        email=saved.get("email", "用户"),
    )


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
