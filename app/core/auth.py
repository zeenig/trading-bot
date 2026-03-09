import base64
import hashlib
import hmac
import json
import time
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.runtime_settings import get_runtime_settings


_bearer = HTTPBearer(auto_error=False)


def _b64_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64_decode(token: str) -> bytes:
    padding = "=" * (-len(token) % 4)
    return base64.urlsafe_b64decode(token + padding)


def _sign(payload_b64: str, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).digest()
    return _b64_encode(digest)


def create_access_token(subject: str, secret: str, expires_in_seconds: int = 60 * 60 * 12) -> str:
    exp = int(time.time()) + max(60, expires_in_seconds)
    payload = {"sub": subject, "exp": exp}
    payload_b64 = _b64_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = _sign(payload_b64, secret)
    return f"{payload_b64}.{signature}"


def decode_access_token(token: str, secret: str) -> Optional[dict]:
    try:
        payload_b64, signature = token.split(".", 1)
        if not hmac.compare_digest(signature, _sign(payload_b64, secret)):
            return None
        payload = json.loads(_b64_decode(payload_b64).decode("utf-8"))
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        return payload
    except Exception:
        return None


def require_auth(credentials: HTTPAuthorizationCredentials = Depends(_bearer)):
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    settings = get_runtime_settings()
    secret = settings.get("AUTH_SECRET", "")
    payload = decode_access_token(credentials.credentials, secret)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    return payload
