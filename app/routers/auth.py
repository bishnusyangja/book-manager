import json
from urllib.parse import parse_qs

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials

from app.config import TOKEN_TTL_SECONDS
from app.db import get_db
from app.schemas import LoginRequest, TokenOut, UserCredentials, UserOut
from app.security import bearer, current_user, hash_password, issue_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(body: UserCredentials, db: aiosqlite.Connection = Depends(get_db)):
    try:
        cur = await db.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (body.username, hash_password(body.password)),
        )
        await db.commit()
    except aiosqlite.IntegrityError:
        raise HTTPException(status.HTTP_409_CONFLICT, "Username already taken")
    return UserOut(id=cur.lastrowid, username=body.username)


async def _read_credentials(request: Request) -> tuple[str, str] | None:
    """Pull username/password from a JSON or form body.

    Returns None for anything unusable (empty, malformed, wrong types), so
    every bad login attempt gets a 401 instead of a 400 validation error.
    """
    raw = await request.body()
    content_type = request.headers.get("content-type", "")
    data: object = None
    if "application/x-www-form-urlencoded" in content_type:
        data = {k: v[0] for k, v in parse_qs(raw.decode(errors="replace")).items()}
    else:
        try:
            data = json.loads(raw) if raw else None
        except ValueError:
            data = None
    if not isinstance(data, dict):
        return None
    username, password = data.get("username"), data.get("password")
    if not isinstance(username, str) or not isinstance(password, str):
        return None
    return username, password


@router.post(
    "/token",
    response_model=TokenOut,
    responses={401: {"description": "Invalid username or password"}},
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {"schema": LoginRequest.model_json_schema()}
            },
        }
    },
)
async def login(request: Request, db: aiosqlite.Connection = Depends(get_db)):
    creds = await _read_credentials(request)
    row = None
    if creds is not None:
        async with db.execute(
            "SELECT id, password_hash FROM users WHERE username = ?", (creds[0],)
        ) as cur:
            row = await cur.fetchone()
    if row is None or not verify_password(creds[1], row["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid username or password")
    token = await issue_token(db, row["id"])
    return TokenOut(token=token, access_token=token, expires_in=TOKEN_TTL_SECONDS)


@router.get("/me", response_model=UserOut)
async def me(user: dict = Depends(current_user)):
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    _: dict = Depends(current_user),
    creds: HTTPAuthorizationCredentials = Depends(bearer),
    db: aiosqlite.Connection = Depends(get_db),
):
    await db.execute("DELETE FROM tokens WHERE token = ?", (creds.credentials,))
    await db.commit()
