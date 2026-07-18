"""Auth: device pairing token (header) + dashboard password (signed cookie)."""
from __future__ import annotations

import hashlib
import hmac
import secrets
from pathlib import Path

from fastapi import Header, HTTPException, Request

from .config import settings

COOKIE_NAME = "ps_session"
_secret_file = Path(settings.data_dir) / ".session_secret"


def _server_secret() -> bytes:
    """Stable per-install secret, persisted so cookies survive restarts."""
    if _secret_file.exists():
        return _secret_file.read_bytes()
    sec = secrets.token_bytes(32)
    _secret_file.parent.mkdir(parents=True, exist_ok=True)
    _secret_file.write_bytes(sec)
    try:
        _secret_file.chmod(0o600)
    except OSError:
        pass
    return sec


def issue_session() -> str:
    return hmac.new(_server_secret(), b"dashboard-ok", hashlib.sha256).hexdigest()


def _valid_session(token: str | None) -> bool:
    return bool(token) and hmac.compare_digest(token, issue_session())


def check_password(pw: str) -> bool:
    return hmac.compare_digest(pw or "", settings.dashboard_password)


# --- FastAPI dependencies ----------------------------------------------------
def require_device(x_device_token: str | None = Header(default=None)) -> None:
    if not hmac.compare_digest(x_device_token or "", settings.device_pairing_token):
        raise HTTPException(status_code=401, detail="bad pairing token")


def require_dashboard(request: Request) -> None:
    if not _valid_session(request.cookies.get(COOKIE_NAME)):
        raise HTTPException(status_code=401, detail="login required")
