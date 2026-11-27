import base64
import hashlib
import hmac
import json
import secrets
import time

import aiosqlite
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import AUTH_ALL_BOOKS, AUTH_REQUIRED, SECRET_KEY, TOKEN_TTL_SECONDS
from app.db import get_db

_ITERATIONS = 200_000
_KEY = hashlib.sha256(SECRET_KEY.encode()).digest()
bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    salt_hex, digest_hex = stored.split("$", 1)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt_hex), _ITERATIONS
    )
    return hmac.compare_digest(digest.hex(), digest_hex)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(payload: str) -> str:
    return _b64(hmac.new(_KEY, payload.encode(), hashlib.sha256).digest())


def issue_token(username: str) -> str:
    """Signed token "<payload>.<signature>". It is checked with SECRET_KEY, not
    looked up in the database, so it survives restarts and redeploys."""
    claims = {
        "sub": username,
        "exp": int(time.time()) + TOKEN_TTL_SECONDS,
        "jti": secrets.token_urlsafe(12),
    }
    payload = _b64(json.dumps(claims, separators=(",", ":")).encode())
    return f"{payload}.{_sign(payload)}"


def decode_token(token: str) -> dict | None:
    """Claims of a valid, unexpired token, or None."""
    try:
        payload, signature = token.split(".")
        if not hmac.compare_digest(signature, _sign(payload)):
            return None
        claims = json.loads(_unb64(payload))
    except (ValueError, TypeError):
        return None
    if not isinstance(claims, dict) or not isinstance(claims.get("sub"), str):
        return None
    if not isinstance(claims.get("exp"), int) or claims["exp"] <= time.time():
        return None
    return claims


async def revoke_token(db: aiosqlite.Connection, claims: dict) -> None:
    await db.execute("DELETE FROM revoked_tokens WHERE expires_at < ?", (time.time(),))
    await db.execute(
        "INSERT OR IGNORE INTO revoked_tokens (jti, expires_at) VALUES (?, ?)",
        (claims["jti"], claims["exp"]),
    )
    await db.commit()


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def valid_claims(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: aiosqlite.Connection = Depends(get_db),
) -> dict:
    """Claims of the request's bearer token; 401 if missing, invalid,
    expired or logged out."""
    if creds is None:
        raise _unauthorized("Missing bearer token")
    claims = decode_token(creds.credentials)
    if claims is None:
        raise _unauthorized("Invalid or expired token")
    async with db.execute(
        "SELECT 1 FROM revoked_tokens WHERE jti = ?", (claims.get("jti"),)
    ) as cur:
        if await cur.fetchone():
            raise _unauthorized("Invalid or expired token")
    return claims


async def current_user(
    claims: dict = Depends(valid_claims),
    db: aiosqlite.Connection = Depends(get_db),
) -> dict:
    async with db.execute(
        "SELECT id, username FROM users WHERE username = ?", (claims["sub"],)
    ) as cur:
        row = await cur.fetchone()
    if row is None:
        raise _unauthorized("Invalid or expired token")
    return dict(row)


async def require_auth(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: aiosqlite.Connection = Depends(get_db),
) -> dict | None:
    """Guard for GET /books; a no-op when AUTH_REQUIRED=false. Only the token
    signature, expiry and logout status are checked, so a valid token keeps
    working even if the database was reset by a redeploy."""
    if not AUTH_REQUIRED:
        return None
    return await valid_claims(creds, db)


async def require_auth_for_book_changes(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: aiosqlite.Connection = Depends(get_db),
) -> dict | None:
    """Guard for the other /books routes; only active when AUTH_ALL_BOOKS=true."""
    if not (AUTH_REQUIRED and AUTH_ALL_BOOKS):
        return None
    return await valid_claims(creds, db)
