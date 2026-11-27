import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from app.db import get_db
from app.schemas import BookIn, BookOut
from app.security import require_auth

router = APIRouter(prefix="/books", tags=["books"], dependencies=[Depends(require_auth)])


async def _get_or_404(db: aiosqlite.Connection, book_id: str) -> dict:
    """Any id that doesn't match a book (including non-numeric ones) is a 404."""
    row = None
    if book_id.isdigit():
        async with db.execute(
            "SELECT id, title, author, year FROM books WHERE id = ?", (int(book_id),)
        ) as cur:
            row = await cur.fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Book not found")
    return dict(row)


@router.post("", response_model=BookOut, status_code=status.HTTP_201_CREATED)
async def create_book(body: BookIn, db: aiosqlite.Connection = Depends(get_db)):
    cur = await db.execute(
        "INSERT INTO books (title, author, year) VALUES (?, ?, ?)",
        (body.title, body.author, body.year),
    )
    await db.commit()
    return BookOut(id=cur.lastrowid, **body.model_dump())


@router.get("", response_model=list[BookOut])
async def list_books(
    author: str | None = None,
    page: int | None = Query(default=None, ge=1),
    limit: int | None = Query(default=None, ge=1, le=100),
    db: aiosqlite.Connection = Depends(get_db),
):
    sql = "SELECT id, title, author, year FROM books"
    params: list = []
    if author:
        sql += " WHERE author LIKE ?"
        params.append(f"%{author}%")
    sql += " ORDER BY id"
    if page is not None or limit is not None:
        size = limit or 10
        sql += " LIMIT ? OFFSET ?"
        params += [size, ((page or 1) - 1) * size]
    async with db.execute(sql, params) as cur:
        return [dict(r) for r in await cur.fetchall()]


@router.get("/{book_id}", response_model=BookOut)
async def get_book(book_id: str, db: aiosqlite.Connection = Depends(get_db)):
    return await _get_or_404(db, book_id)


@router.put(
    "/{book_id}",
    response_model=BookOut,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": BookIn.model_json_schema()}},
        }
    },
)
async def update_book(book_id: str, request: Request, db: aiosqlite.Connection = Depends(get_db)):
    # Check the book exists before validating the body, so a missing book is
    # always a 404 whatever the body looks like.
    book = await _get_or_404(db, book_id)
    try:
        body = BookIn.model_validate_json(await request.body())
    except ValidationError as e:
        raise RequestValidationError(
            [{**err, "loc": ("body", *err["loc"])} for err in e.errors()]
        )
    await db.execute(
        "UPDATE books SET title = ?, author = ?, year = ? WHERE id = ?",
        (body.title, body.author, body.year, book["id"]),
    )
    await db.commit()
    return BookOut(id=book["id"], **body.model_dump())


@router.delete("/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_book(book_id: str, db: aiosqlite.Connection = Depends(get_db)):
    book = await _get_or_404(db, book_id)
    await db.execute("DELETE FROM books WHERE id = ?", (book["id"],))
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
