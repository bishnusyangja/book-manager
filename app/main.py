import logging
from contextlib import asynccontextmanager
from typing import Any

import aiosqlite
from fastapi import Body, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config import ADMIN_PASSWORD, ADMIN_USERNAME, DB_PATH
from app.db import init_db
from app.routers import auth, books
from app.security import hash_password


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (username, password_hash) VALUES (?, ?)",
            (ADMIN_USERNAME, hash_password(ADMIN_PASSWORD)),
        )
        await db.commit()
    yield


logger = logging.getLogger("book_manager")

app = FastAPI(title="Book Manager API", lifespan=lifespan)
app.include_router(auth.router)
app.include_router(books.router)


def _describe(error: dict) -> dict:
    """Turn one pydantic error into {"field", "message"} for API clients."""
    loc = [str(p) for p in error["loc"][1:]]  # drop "body" / "query" / "path"
    if error["type"] == "json_invalid":
        return {"field": "body", "message": "Request body is not valid JSON"}
    if not loc:
        if error["type"] == "missing":
            return {"field": "body", "message": "Request body is required"}
        return {"field": "body", "message": "Request body must be a JSON object"}
    return {"field": ".".join(loc), "message": error["msg"]}


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    # Invalid input -> 400 Bad Request (FastAPI's default is 422).
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "detail": "Validation failed",
            "errors": [_describe(e) for e in exc.errors()],
        },
    )


@app.exception_handler(Exception)
async def unexpected_error(_: Request, exc: Exception):
    # Never leak a stack trace; always answer with JSON.
    logger.exception("Unhandled error", exc_info=exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


@app.get("/", tags=["meta"])
async def root():
    return {"message": "Welcome to Book Manager By Bishnu"}


@app.get("/ping", tags=["meta"])
async def ping():
    return {"success": True}


@app.post("/echo", tags=["meta"])
async def echo(payload: Any = Body(default=None)):
    return payload
