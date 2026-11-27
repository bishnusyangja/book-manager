import os

DB_PATH = os.getenv("DB_PATH", "books.db")
TOKEN_TTL_SECONDS = int(os.getenv("TOKEN_TTL_SECONDS", "86400"))  # 24 hours
# Set AUTH_REQUIRED=false to make /books public.
AUTH_REQUIRED = os.getenv("AUTH_REQUIRED", "true").lower() != "false"
# Seeded on startup so there is always a user that can log in.
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "password")
# Key that signs login tokens. Tokens stay valid across restarts and redeploys
# as long as this stays the same. If unset, it is derived from the admin
# credentials, which are stable between deploys; set SECRET_KEY in production.
SECRET_KEY = os.getenv("SECRET_KEY") or f"book-manager:{ADMIN_USERNAME}:{ADMIN_PASSWORD}"
