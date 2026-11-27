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

In the container the app runs on [Hypercorn](https://hypercorn.readthedocs.io/), an async ASGI server. `docker/entrypoint.sh` does three things before starting it:
- makes the data folder writable (hosts often mount volumes owned by root), then drops to the unprivileged `appuser`
- listens on `$PORT`
- listens on both IPv6 and IPv4 when the container supports IPv6

Server settings are in `docker/hypercorn.toml`.

### With nginx (docker compose)

For a self-hosted server, `docker-compose.yml` runs nginx in front of the app:

```bash
ADMIN_PASSWORD=something-strong docker compose up -d --build
```

nginx listens on port 80 (set `NGINX_PORT` to change it) and forwards to the app. Its config is in `nginx/nginx.conf`. `GET /nginx-health` checks nginx itself.

## Deploy to Railway

Railway builds the `Dockerfile` directly and has its own proxy, so nginx is not used there. `railway.json` sets the Dockerfile builder, the `/ping` health check and the restart policy.

1. New Project → **Deploy from GitHub repo** → pick this repo, branch `master`.
2. Add a **volume** with mount path `/app/data`.
3. Add the variables **before the first deploy**:
   - `ADMIN_PASSWORD`: a strong password
   - `PORT`: `8000`
4. Settings → Networking → **Generate Domain** with target port **`8000`**.

The domain's target port must match `PORT`, or Railway returns `502 Bad Gateway`. The deploy log should show `Starting Hypercorn on [::]:8000`.

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

## Managing dependencies

```bash
uv add <package>          # add a runtime dependency
uv add --dev <package>    # add a dev-only dependency (e.g. test tools)
uv remove <package>
```

## API endpoints

Base URL when running locally: `http://127.0.0.1:8000`

All request and response bodies are JSON. Endpoints marked **Auth** need the header `Authorization: Bearer <token>`. A missing, invalid, expired or revoked token returns `401` with the header `WWW-Authenticate: Bearer`.

### All URLs

| Method | URL | Auth | Description | Success | Errors |
|---|---|---|---|---|---|
| GET | `/` | — | Welcome message | `200` | — |
| GET | `/ping` | — | Health check | `200` | — |
| POST | `/echo` | — | Returns the JSON body it receives | `200` | `400` |
| POST | `/auth/register` | — | Create a user | `201` | `400`, `409` |
| POST | `/auth/token` | — | Log in and get a bearer token | `200` | `400`, `401` |
| GET | `/auth/me` | ✓ | The current user | `200` | `401` |
| POST | `/auth/logout` | ✓ | Revoke the current token | `204` | `401` |
| GET | `/books` | ✓ | List, search and paginate books | `200` | `400`, `401` |
| POST | `/books` | ✓ | Create a book | `201` | `400`, `401` |
| GET | `/books/{book_id}` | ✓ | Get one book | `200` | `400`, `401`, `404` |
| PUT | `/books/{book_id}` | ✓ | Replace a book | `200` | `400`, `401`, `404` |
| DELETE | `/books/{book_id}` | ✓ | Delete a book | `204` | `400`, `401`, `404` |
| GET | `/docs` | — | Interactive API docs (Swagger UI) | `200` | — |
| GET | `/redoc` | — | Alternative API docs (ReDoc) | `200` | — |
| GET | `/openapi.json` | — | OpenAPI specification | `200` | — |
| GET | `/docs/oauth2-redirect` | — | Swagger UI login helper | `200` | — |

`/docs`, `/redoc`, `/openapi.json` and `/docs/oauth2-redirect` are generated by FastAPI. `/docs/oauth2-redirect` is a helper page for Swagger UI's login and isn't meant to be called directly.

### General

#### `GET /`
Welcome message.
```json
{"message": "Welcome to Book Manager By Bishnu"}
```

#### `GET /ping`
Health check.
```json
{"success": true}
```

#### `POST /echo`
Returns the request body unchanged. Any valid JSON is accepted (object, array, string, number, boolean or null). An empty body returns `null`, and malformed JSON returns `400`.

### Authentication

#### `POST /auth/register`
Creates a user.

| Field | Type | Rules |
|---|---|---|
| `username` | string | required, 3–50 characters, unique |
| `password` | string | required, 6–128 characters |

Response `201`:
```json
{"id": 2, "username": "alice"}
```
`409` if the username is already taken.

#### `POST /auth/token`
Logs in. The body is the same as `/auth/register`.

Response `200`:
```json
{
  "token": "C_YSG4-n62XxXi3SkvWCcMRNYwYLKNF038aPacFg_Us",
  "access_token": "C_YSG4-n62XxXi3SkvWCcMRNYwYLKNF038aPacFg_Us",
  "token_type": "bearer",
  "expires_in": 3600
}
```
`token` and `access_token` hold the same value. `expires_in` is in seconds (set by `TOKEN_TTL_SECONDS`). Every login creates a new token. A wrong username or password returns `401`.

#### `GET /auth/me` — Auth
Returns the logged-in user.
```json
{"id": 1, "username": "admin"}
```

#### `POST /auth/logout` — Auth
Revokes the token used in the request. Other tokens for the same user keep working. Returns `204` with no body.

### Books

All `/books` endpoints need a token unless `AUTH_REQUIRED=false`.

Book fields:

| Field | Type | Rules |
|---|---|---|
| `id` | integer | set by the server |
| `title` | string | required, 1–255 characters |
| `author` | string | required, 1–255 characters |
| `year` | integer or null | optional, 0–9999 |

#### `GET /books` — Auth
Returns a JSON array of books, ordered by `id`.

| Query parameter | Type | Description |
|---|---|---|
| `author` | string | Partial, case-insensitive match on author |
| `page` | integer ≥ 1 | Page number. Defaults to `1` when only `limit` is given |
| `limit` | integer 1–100 | Page size. Defaults to `10` when only `page` is given |

Without `page` or `limit`, all matching books are returned. A page past the end returns `[]`. Examples:
- `/books?author=orwell`
- `/books?page=2&limit=2`
- `/books?author=orwell&page=1&limit=5`

#### `POST /books` — Auth
Creates a book. Request:
```json
{"title": "Dune", "author": "Frank Herbert", "year": 1965}
```
Response `201`:
```json
{"id": 1, "title": "Dune", "author": "Frank Herbert", "year": 1965}
```

#### `GET /books/{book_id}` — Auth
Returns one book, or `404` if it doesn't exist.

#### `PUT /books/{book_id}` — Auth
Replaces all fields of a book. The body is the same as `POST /books`. A field left out (such as `year`) is cleared. Returns the updated book, or `404`.

#### `DELETE /books/{book_id}` — Auth
Deletes a book. Returns `204` with no body, or `404`.

### Error responses

| Status | When | Body |
|---|---|---|
| `400` | Invalid body, malformed JSON, bad query parameter or non-numeric `book_id` | `{"detail": "Validation failed", "errors": [{"field": "...", "message": "..."}]}` |
| `401` | Missing, invalid, expired or revoked token, or wrong login | `{"detail": "..."}` |
| `404` | Book not found | `{"detail": "Book not found"}` |
| `409` | Username already taken | `{"detail": "Username already taken"}` |

Validation errors return `400` instead of FastAPI's default `422`.

### Implementation notes

- **Storage:** SQLite through `aiosqlite`, with tables `users`, `tokens` and `books`. They're created at startup if missing.
- **Passwords:** hashed with PBKDF2-HMAC-SHA256 (200,000 iterations, random 16-byte salt per user).
- **Tokens:** random 32-byte URL-safe strings stored in the `tokens` table with an expiry time. Expired tokens are cleaned up on each login.
- **Default user:** `ADMIN_USERNAME` / `ADMIN_PASSWORD` is created at startup if it doesn't exist yet. Changing the password variable later doesn't update an existing user.
