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
    CookieController 不提供 ready() 方法。

    控制器创建后即可调用，因此直接返回 True。
    """
    return True


def get_cookie(
    cookie_store: Any,
    name: str,
    default: Optional[str] = None,
) -> Optional[str]:

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
        print(f"⚠️ 读取 Cookie {name!r} 失败: {error}")
        return default

    if value in (None, ""):
        return default

    return str(value)


def set_cookie(
    cookie_store: Any,
    name: str,
    value: str,
) -> None:
    """
    使用 CookieController 写入 Cookie。

    敏感值先加密，再写入浏览器。
    """
    cookie_name = _controller_cookie_name(name)
    encrypted_value = _encrypt_cookie_value(value)

    cookie_store.set(
        cookie_name,
        encrypted_value,
    )

def delete_cookie(
    cookie_store: Any,
    name: str,
) -> None:
    """使用 CookieController 删除指定 Cookie。"""
    cookie_name = _controller_cookie_name(name)

    try:
        cookie_store.remove(cookie_name)
    except KeyError:
        # Cookie 原本不存在，等同于已删除
        pass

def save_cookies(cookie_store: Any) -> None:
    """
    CookieController 的 set() 和 remove() 会直接生效，
    不需要额外调用 save()。
    保留此函数是为了兼容现有业务代码。
    """
    return