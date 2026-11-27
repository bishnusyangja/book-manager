import os

DB_PATH = os.getenv("DB_PATH", "books.db")
TOKEN_TTL_SECONDS = int(os.getenv("TOKEN_TTL_SECONDS", "86400"))  # 24 hours
# GET /books (the book list) needs a token unless AUTH_REQUIRED=false.
AUTH_REQUIRED = os.getenv("AUTH_REQUIRED", "true").lower() != "false"
# Set AUTH_ALL_BOOKS=true to also require a token for creating, reading one,
# updating and deleting books. Off by default to match the API Quest spec,
# which only protects GET /books.
AUTH_ALL_BOOKS = os.getenv("AUTH_ALL_BOOKS", "false").lower() == "true"
# Seeded on startup so there is always a user that can log in.
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "password")
# Key that signs login tokens. Tokens stay valid across restarts and redeploys
# as long as this stays the same. If unset, it is derived from the admin
# credentials, which are stable between deploys; set SECRET_KEY in production.
SECRET_KEY = os.getenv("SECRET_KEY") or f"book-manager:{ADMIN_USERNAME}:{ADMIN_PASSWORD}"
