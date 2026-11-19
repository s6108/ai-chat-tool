"""Input checks and accidental resend protection for Auth email requests.

These checks cannot prove a mailbox exists and do not replace Supabase limits.
Never log recipient addresses or persist them in the cooldown state.
"""

import math
import re

AUTH_EMAIL_INTERVAL = 60
_LAST_ATTEMPT = "auth_email_last_attempt"
_LOCAL = re.compile(r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~.-]+\Z")
_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")


def normalize_auth_email(value: str) -> str:
    email = value.strip()
    if email.count("@") != 1:
        raise ValueError("auth_email_invalid")
    local, domain = email.split("@")
    try:
        domain = domain.encode("idna").decode("ascii").lower()
    except UnicodeError:
        raise ValueError("auth_email_invalid") from None
    labels = domain.split(".")
    if (
        not _LOCAL.fullmatch(local)
        or len(local) > 64
        or local.startswith(".")
        or local.endswith(".")
        or ".." in local
        or len(labels) < 2
        or any(not _LABEL.fullmatch(label) for label in labels)
        or labels[-1].isdigit()
        or len(f"{local}@{domain}") > 254
    ):
        raise ValueError("auth_email_invalid")
    # Reserved examples must never trigger real production email delivery.
    if labels[-1] in {"invalid", "test", "localhost", "example"} or any(
        domain == reserved or domain.endswith("." + reserved)
        for reserved in ("example.com", "example.net", "example.org")
    ):
        raise ValueError("auth_email_invalid")
    return f"{local}@{domain}"


def email_wait_seconds(state, now: float) -> int:
    last = state.get(_LAST_ATTEMPT)
    if last is None:
        return 0
    return max(0, math.ceil(AUTH_EMAIL_INTERVAL - (now - last)))


def mark_email_attempt(state, now: float) -> None:
    state[_LAST_ATTEMPT] = now


def auth_email_error_key(error) -> str | None:
    code = str(getattr(error, "code", ""))
    message = str(error).lower()
    if code == "over_email_send_rate_limit" or "email rate limit" in message:
        return "auth_email_rate_limited"
    if "for security purposes" in message and "seconds" in message:
        return "auth_email_rate_limited"
    if code == "email_address_not_authorized":
        return "auth_email_unavailable"
    if "error sending" in message and "email" in message:
        return "auth_email_unavailable"
    return None
