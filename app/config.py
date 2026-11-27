import os

DB_PATH = os.getenv("DB_PATH", "books.db")
TOKEN_TTL_SECONDS = int(os.getenv("TOKEN_TTL_SECONDS", "3600"))
# Set AUTH_REQUIRED=false to make /books public.
AUTH_REQUIRED = os.getenv("AUTH_REQUIRED", "true").lower() != "false"
# Seeded on startup so there is always a user that can log in.
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "password")
