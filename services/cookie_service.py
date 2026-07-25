import base64
from functools import lru_cache
from typing import Any, Optional

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from streamlit_cookies_controller import CookieController


from config import COOKIE_BACKEND, COOKIE_PASSWORD


COOKIE_PREFIX = "mango_ai_"
COOKIE_ENCRYPTION_SALT = b"mango-ai-cookie-controller-v1"

LEGACY_BACKEND = "legacy"
CONTROLLER_BACKEND = "controller"


def _get_backend() -> str:
    """
    返回当前 Cookie 后端名称。

    未配置或配置错误时，保守回退到 legacy，
    防止因环境变量错误导致登录系统失效。
    """
    backend = str(COOKIE_BACKEND or LEGACY_BACKEND).strip().lower()

    if backend not in {LEGACY_BACKEND, CONTROLLER_BACKEND}:
        print(
            f"⚠️ 未知 COOKIE_BACKEND={backend!r}，"
            f"自动回退到 {LEGACY_BACKEND}"
        )
        return LEGACY_BACKEND

    return backend


@lru_cache(maxsize=1)
def _get_fernet() -> Fernet:
    """
    使用 COOKIE_PASSWORD 派生稳定的 Fernet 密钥。

    仅 controller 后端使用这一层加密。
    # Cookie 统一使用 CookieController
    """
    if not COOKIE_PASSWORD:
        raise RuntimeError("COOKIE_PASSWORD 未配置")

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=COOKIE_ENCRYPTION_SALT,
        iterations=600_000,
    )

    derived_key = kdf.derive(
        str(COOKIE_PASSWORD).encode("utf-8")
    )

    fernet_key = base64.urlsafe_b64encode(derived_key)

    return Fernet(fernet_key)


def _controller_cookie_name(name: str) -> str:
    """为 controller 后端的 Cookie 添加统一前缀。"""
    return f"{COOKIE_PREFIX}{name}"


def _encrypt_cookie_value(value: Any) -> str:
    """把 Cookie 内容加密成可写入浏览器的字符串。"""
    if value is None:
        return ""

    plaintext = str(value).encode("utf-8")

    return (
        _get_fernet()
        .encrypt(plaintext)
        .decode("utf-8")
    )


def _decrypt_cookie_value(value: Any) -> Optional[str]:
    """
    解密 controller 后端保存的 Cookie。

    内容为空、损坏、密码不一致时返回 None，
    不让无效 Cookie 中断整个应用。
    """
    if value is None:
        return None

    encrypted_value = str(value).strip()

    if not encrypted_value:
        return None

    try:
        return (
            _get_fernet()
            .decrypt(encrypted_value.encode("utf-8"))
            .decode("utf-8")
        )
    except (InvalidToken, ValueError, TypeError):
        return None


def create_cookie_manager() -> CookieController:
    """创建 Mango AI 的 Cookie 控制器。"""
    print("🍪 Cookie backend: controller")
    return CookieController()

def cookies_ready(cookie_store: Any) -> bool:
    """
    判断 Cookie 组件是否已加载。

    旧后端需要调用 ready()。
    新后端没有 ready()，因此直接视为可用。
    """
    if _get_backend() == CONTROLLER_BACKEND:
        return True

    try:
        return bool(cookie_store.ready())
    except Exception as error:
        print(f"⚠️ Cookie ready 检查失败：{error}")
        return False


def get_cookie(
    cookie_store: Any,
    name: str,
    default: Optional[str] = None,
) -> Optional[str]:
    """统一读取 Cookie。"""
    backend = _get_backend()

    try:
        if backend == CONTROLLER_BACKEND:
            raw_value = cookie_store.get(
                _controller_cookie_name(name)
            )

            value = _decrypt_cookie_value(raw_value)
        else:
            value = cookie_store.get(name)

    except Exception as error:
        print(f"⚠️ 读取 Cookie {name!r} 失败：{error}")
        return default

    if value in (None, ""):
        return default

    return str(value)


def set_cookie(
    cookie_store: Any,
    name: str,
    value: Any,
) -> None:
    """
    统一设置 Cookie。

    legacy 后端只写入内存，稍后由 save_cookies() 保存。
    controller 后端调用 set() 时立即写入浏览器。
    """
    backend = _get_backend()

    try:
        if backend == CONTROLLER_BACKEND:
            encrypted_value = _encrypt_cookie_value(value)

            cookie_store.set(
                _controller_cookie_name(name),
                encrypted_value,
            )
        else:
            cookie_store[name] = (
                "" if value is None else str(value)
            )

    except Exception as error:
        print(f"⚠️ 设置 Cookie {name!r} 失败：{error}")
        raise


def delete_cookie(
    cookie_store: Any,
    name: str,
) -> None:
    """
    删除 Cookie。
    controller 不存在时忽略错误。
    """

    backend = _get_backend()

    try:

        if backend == CONTROLLER_BACKEND:

            cookie_name = _controller_cookie_name(name)

            try:
                print("DEBUG delete cookie:", cookie_name)
                cookie_store.remove(cookie_name)

            except KeyError:
                pass

            except Exception as error:
                print(
                    f"⚠️ 删除 Cookie {cookie_name} 时忽略异常: {error}"
                )

        else:
            cookie_store[name] = ""

    except Exception as error:
        print(
            f"⚠️ Cookie 删除失败，继续退出流程: {error}"
        )


def save_cookies(cookie_store: Any) -> None:
    """
    统一保存 Cookie。

    legacy:
        必须调用 save() 才真正写入浏览器。

    controller:
        set() 和 remove() 已即时生效，因此无需额外保存。
    """
    if _get_backend() == CONTROLLER_BACKEND:
        return

    cookie_store.save()