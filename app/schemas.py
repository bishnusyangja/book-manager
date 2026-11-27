from pydantic import BaseModel, Field


class UserCredentials(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6, max_length=128)


class UserOut(BaseModel):
    id: int
    username: str


class TokenOut(BaseModel):
    token: str
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class BookIn(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    author: str = Field(min_length=1, max_length=255)
    year: int | None = Field(default=None, ge=0, le=9999)


class BookOut(BookIn):
    id: int
