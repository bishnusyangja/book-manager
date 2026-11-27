import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, status
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


@router.post("/token", response_model=TokenOut)
async def login(body: LoginRequest, db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute(
        "SELECT id, password_hash FROM users WHERE username = ?", (body.username,)
    ) as cur:
        row = await cur.fetchone()
    if row is None or not verify_password(body.password, row["password_hash"]):
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
