"""Cookie session auth (HMAC-signed, stateless)."""

import base64
import hashlib
import hmac
import time

from fastapi import HTTPException, Request, WebSocket

from .settings import ADMIN_PASS, ADMIN_USER, SECRET_KEY, SESSION_DAYS

COOKIE_NAME = "jb_session"


def _sign(payload: str) -> str:
    return hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()


def make_token(user: str) -> str:
    payload = f"{user}|{int(time.time()) + SESSION_DAYS * 86400}"
    encoded = base64.urlsafe_b64encode(payload.encode()).decode()
    return f"{encoded}.{_sign(payload)}"


def verify_token(token: str | None) -> str | None:
    if not token or "." not in token:
        return None
    encoded, sig = token.rsplit(".", 1)
    try:
        payload = base64.urlsafe_b64decode(encoded.encode()).decode()
        user, exp = payload.rsplit("|", 1)
        exp = int(exp)
    except Exception:
        return None
    if not hmac.compare_digest(_sign(payload), sig) or exp < time.time():
        return None
    return user


def check_credentials(username: str, password: str) -> bool:
    ok_user = hmac.compare_digest(username.encode(), ADMIN_USER.encode())
    ok_pass = hmac.compare_digest(password.encode(), ADMIN_PASS.encode())
    return ok_user and ok_pass


def require_auth(request: Request) -> str:
    user = verify_token(request.cookies.get(COOKIE_NAME))
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def ws_authenticated(ws: WebSocket) -> bool:
    return verify_token(ws.cookies.get(COOKIE_NAME)) is not None


def is_https(request: Request) -> bool:
    return request.url.scheme == "https" or request.headers.get("x-forwarded-proto", "") == "https"
