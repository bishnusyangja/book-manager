# book-manager

A REST API for managing books, built with [FastAPI](https://fastapi.tiangolo.com/) and async SQLite ([aiosqlite](https://github.com/omnilib/aiosqlite)). It includes user registration and bearer-token authentication, and covers the levels of the [API Quest backend challenge](https://www.desent.io/coding-test-backend).

## Requirements

- Python 3.13 or newer
- [uv](https://docs.astral.sh/uv/) for dependencies and the virtual environment
- Docker (optional, only for running in a container)

## Run locally

```bash
# Install dependencies (creates .venv from uv.lock)
uv sync

# Start the dev server with auto-reload
uv run uvicorn app.main:app --reload
```

The API is now at http://127.0.0.1:8000. Interactive docs are at http://127.0.0.1:8000/docs.

The SQLite database file (`books.db` by default) is created on first start. A default user `admin` / `password` is also created, so you can log in right away. **Change this password before deploying** (see [Configuration](#configuration)).

## Run with Docker

```bash
docker build -t book-manager .
docker run -p 8000:8000 -v book-data:/app/data book-manager
```

The `-v book-data:/app/data` volume keeps the database between container restarts. Pass settings with `-e`, for example:

```bash
docker run -p 8000:8000 -v book-data:/app/data \
  -e ADMIN_PASSWORD=something-strong \
  book-manager
```

## Run the tests

```bash
uv run pytest
```

Each test uses its own temporary database, so the tests never touch `books.db`.

## Configuration

All settings are environment variables:

| Variable | Default | Description |
|---|---|---|
| `DB_PATH` | `books.db` (`/app/data/books.db` in Docker) | Path to the SQLite database file |
| `ADMIN_USERNAME` | `admin` | Username of the user created at startup |
| `ADMIN_PASSWORD` | `password` | Password of the user created at startup |
| `TOKEN_TTL_SECONDS` | `3600` | How long a login token stays valid |
| `AUTH_REQUIRED` | `true` | Set to `false` to make `/books` endpoints public |
| `PORT` | `8000` | Port the server listens on (Docker only) |

## Authentication

1. Get a token (or register first with `POST /auth/register`):
   ```bash
   curl -X POST http://127.0.0.1:8000/auth/token \
     -H 'Content-Type: application/json' \
     -d '{"username": "admin", "password": "password"}'
   ```
2. Send it in the `Authorization` header on `/books` requests:
   ```bash
   curl http://127.0.0.1:8000/books -H 'Authorization: Bearer <token>'
   ```

## API endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/ping` | — | Health check, returns `{"success": true}` |
| POST | `/echo` | — | Returns the JSON body it receives |
| POST | `/auth/register` | — | Create a user (`201`, or `409` if the username is taken) |
| POST | `/auth/token` | — | Log in and get a bearer token (`401` on wrong credentials) |
| GET | `/auth/me` | ✓ | The current user |
| POST | `/auth/logout` | ✓ | Revoke the current token (`204`) |
| GET | `/books` | ✓ | List books. Optional `?author=` (partial, case-insensitive), `?page=` and `?limit=` (max 100) |
| POST | `/books` | ✓ | Create a book (`201`) |
| GET | `/books/{id}` | ✓ | Get one book (`404` if not found) |
| PUT | `/books/{id}` | ✓ | Replace a book |
| DELETE | `/books/{id}` | ✓ | Delete a book (`204`) |

A book looks like this (`year` is optional):

```json
{"id": 1, "title": "Dune", "author": "Frank Herbert", "year": 1965}
```

Invalid input returns `400` with the fields that failed:

```json
{"detail": "Validation failed", "errors": [{"field": "title", "message": "Field required"}]}
```

## Project structure

```
app/
├── main.py          # App setup, startup, error handler, /ping and /echo
├── config.py        # Settings from environment variables
├── db.py            # SQLite schema and connections
├── schemas.py       # Request and response models
├── security.py      # Password hashing and token checks
└── routers/
    ├── auth.py      # /auth endpoints
    └── books.py     # /books endpoints
tests/               # pytest suite
Dockerfile
pyproject.toml       # Dependencies (managed by uv)
uv.lock
```

## Managing dependencies

```bash
uv add <package>          # add a runtime dependency
uv add --dev <package>    # add a dev-only dependency (e.g. test tools)
uv remove <package>
```
