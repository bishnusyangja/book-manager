from typing import Annotated

from pydantic import BaseModel, Field, StrictInt, StringConstraints

# Text that must contain something besides spaces: surrounding whitespace is
# trimmed first, so "   " counts as empty and is rejected with 400.
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


class UserCredentials(BaseModel):
    username: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=50)]
    password: str = Field(min_length=6, max_length=128)


class LoginRequest(BaseModel):
    # No length rules here: any wrong or missing credentials must give 401,
    # not a 400 validation error.
    username: str = ""
    password: str = ""


class UserOut(BaseModel):
    id: int
    username: str


class TokenOut(BaseModel):
    token: str
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class BookIn(BaseModel):
    title: Name
    author: Name
    # Strict: true/false or "1965" are rejected instead of silently converted.
    year: StrictInt | None = Field(default=None, ge=0, le=9999)


class BookOut(BookIn):
    id: int
