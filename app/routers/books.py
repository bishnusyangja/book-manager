import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.db import get_db
from app.schemas import BookIn, BookOut
from app.security import require_auth

router = APIRouter(prefix="/books", tags=["books"], dependencies=[Depends(require_auth)])


async def _get_or_404(db: aiosqlite.Connection, book_id: int) -> dict:
    async with db.execute(
        "SELECT id, title, author, year FROM books WHERE id = ?", (book_id,)
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
async def get_book(book_id: int, db: aiosqlite.Connection = Depends(get_db)):
    return await _get_or_404(db, book_id)


@router.put("/{book_id}", response_model=BookOut)
async def update_book(book_id: int, body: BookIn, db: aiosqlite.Connection = Depends(get_db)):
    await _get_or_404(db, book_id)
    await db.execute(
        "UPDATE books SET title = ?, author = ?, year = ? WHERE id = ?",
        (body.title, body.author, body.year, book_id),
    )
    await db.commit()
    return BookOut(id=book_id, **body.model_dump())


@router.delete("/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_book(book_id: int, db: aiosqlite.Connection = Depends(get_db)):
    await _get_or_404(db, book_id)
    await db.execute("DELETE FROM books WHERE id = ?", (book_id,))
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
