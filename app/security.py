import hashlib
import hmac
import secrets
import time

import aiosqlite
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import AUTH_REQUIRED, TOKEN_TTL_SECONDS
from app.db import get_db

_ITERATIONS = 200_000
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


async def issue_token(db: aiosqlite.Connection, user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    await db.execute("DELETE FROM tokens WHERE expires_at < ?", (time.time(),))
    await db.execute(
        "INSERT INTO tokens (token, user_id, expires_at) VALUES (?, ?, ?)",
        (token, user_id, time.time() + TOKEN_TTL_SECONDS),
    )
    await db.commit()
    return token


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: aiosqlite.Connection = Depends(get_db),
) -> dict:
    if creds is None:
        raise _unauthorized("Missing bearer token")
    async with db.execute(
        "SELECT u.id, u.username FROM tokens t JOIN users u ON u.id = t.user_id "
        "WHERE t.token = ? AND t.expires_at > ?",
        (creds.credentials, time.time()),
    ) as cur:
        row = await cur.fetchone()
    if row is None:
        raise _unauthorized("Invalid or expired token")
    return dict(row)


async def require_auth(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: aiosqlite.Connection = Depends(get_db),
) -> dict | None:
    """Guard for /books; a no-op when AUTH_REQUIRED=false."""
    if not AUTH_REQUIRED:
        return None
    return await current_user(creds, db)
