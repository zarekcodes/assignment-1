# Library Management System API

The Library Management System API is a backend that library staff use to manage **Members** and the **Books** they borrow. Staff can create, view, update, and delete both resources. Each Book is borrowed by exactly one existing Member, and a Member can borrow many Books.

This is Assignment 3 for SDEV 3310. Assignment 2 stored data in **PostgreSQL** through **SQLAlchemy 2.x** and **Psycopg** and organized the code into routers, services, repositories, ORM models, and schemas, with the original in-memory storage kept as an alternative backend. Assignment 3 keeps all of that and adds:

- **Bearer-token access control.** Every Book and Member operation needs a valid token. A *member* token may read; only an *administrator* token may create, update, or delete.
- **An automated pytest suite.** Unit tests, integration tests against a disposable PostgreSQL container (Testcontainers), and OpenAPI conformance, negative, and security tests (including Schemathesis).

## Prerequisites

- [uv](https://docs.astral.sh/uv/) — manages the Python version, virtual environment, and dependencies
- [PostgreSQL](https://www.postgresql.org/download/) 14 or later, running locally on port `5432` (only needed to *run the API* with the database backend)
- [Docker](https://docs.docker.com/get-started/get-docker/) (Docker Desktop on Windows/macOS, Docker Engine on Linux), running, to *run the test suite*. The integration tests start a throwaway PostgreSQL container; they never use your local database.
- Git

### Install uv

macOS and Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Windows PowerShell:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Restart your terminal, then check the installation with `uv --version`.

## 1. Get the code

```bash
git clone <repository-url>
cd <repository-folder>
git switch assignment-3
```

## 2. Set up PostgreSQL

Install PostgreSQL and make sure the server is running:

- **Windows:** use the [EDB installer](https://www.postgresql.org/download/windows/). It creates a `postgres` user and starts the server as a service. When it asks for a password, use `postgres` for this local course project, or use your own and put it in `.env` in step 3.
- **macOS:** `brew install postgresql@18` and then `brew services start postgresql@18`.
- **Linux:** install the `postgresql` package from your distribution, initialize the cluster if your distribution requires it, and start the `postgresql` service.

Then create the database. From the repository root, run:

```bash
psql -d postgres -f scripts/setup_database.sql
```

If `psql` asks who you are or refuses the connection, add the user and host: `psql -h localhost -U postgres -d postgres -f scripts/setup_database.sql`. On Windows, if `psql` is not on your `PATH`, use its full path, for example `& "C:\Program Files\PostgreSQL\18\bin\psql.exe"`.

The script creates a `postgres` login role (password `postgres`) if one does not exist, and a `library_management` database owned by it. It is safe to run more than once; it never deletes existing data.

You do not create tables yourself. On startup, the API creates the `members` and `books` tables if they are missing.

## 3. Configure the application

Copy the sample environment file:

```bash
cp .env.example .env
```

| Setting | Default | Purpose |
|---|---|---|
| `STORAGE_BACKEND` | `database` | `database` stores data in PostgreSQL. `memory` stores it in Python lists that are lost when the API stops. |
| `DATABASE_URL` | none | Required when `STORAGE_BACKEND=database`. Format: `postgresql+psycopg://USER:PASSWORD@HOST:PORT/DATABASE` |
| `DATABASE_ECHO_SQL` | `false` | Set to `true` to print every SQL statement SQLAlchemy sends to PostgreSQL. |
| `DEMO_MEMBER_TOKEN` | none (required) | Bearer token for the **member** request role (read-only). |
| `DEMO_ADMIN_TOKEN` | none (required) | Bearer token for the **administrator** request role (read and write). Must differ from `DEMO_MEMBER_TOKEN`. |

The sample `DATABASE_URL` matches the setup script:

```text
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/library_management
```

`postgres:postgres` is a local development credential only. Never reuse it in production; real deployments load credentials from a secret manager or protected environment configuration. `.env` is listed in `.gitignore` and must never be committed.

The sample tokens, `member-demo-token` and `admin-demo-token`, are safe classroom demonstration values. Like the database password, the tokens have **no default in source code**, so the API refuses to start until they are configured. Change them in `.env` for anything other than local practice.

Settings are read from environment variables and `.env` **once, at startup**, and are validated by a typed `Settings` class (`app/config.py`). The API refuses to start if `STORAGE_BACKEND` is not `database` or `memory`, if the database backend is selected without a `DATABASE_URL`, or if either token is missing, empty, or the two tokens are the same.

## 4. Install and run

```bash
uv sync
uv run uvicorn app.main:app --reload
```

- `uv sync` downloads Python 3.13 if needed, creates `.venv/`, and installs the exact versions recorded in `uv.lock`, including the `dev` dependency group used by the tests.
- `app.main:app` tells Uvicorn to load the `app` object from `app/main.py`.
- `--reload` restarts the server when source code changes.

The server runs at `http://localhost:8000`. To confirm the tables were created:

```bash
psql -h localhost -U postgres -d library_management -c '\d'
```

### Verify that data persists

1. Create a Member (example below).
2. Stop the server with `Ctrl+C` and start it again.
3. `GET /members` still returns the Member.

With `STORAGE_BACKEND=memory`, the same steps return an empty list, because in-memory data lives only as long as the process.

## 5. Run the tests

Make sure Docker is running, then from the repository root:

```bash
uv run pytest
```

The first run downloads the `postgres:18` image (about 150 MB), so it takes longer. Later runs finish in about 25 seconds. No `.env` file, local PostgreSQL server, or running API is needed: the tests configure themselves.

### What the test run does with Docker

- [Testcontainers](https://testcontainers.com/) starts **one** `postgres:18` container for the whole `pytest` command, on a random free port, and removes it when the run ends.
- Before each database test, the `members` and `books` tables are dropped and recreated from the ORM models, so every test starts empty and no test depends on another.
- The tests set `DATABASE_URL`, `STORAGE_BACKEND`, and both tokens themselves. Environment variables take priority over `.env`, so your local `library_management` database and your `.env` values are never used.
- Unit tests don't use Docker. `uv run pytest tests/unit` works with Docker stopped.

### Useful commands

```bash
uv run pytest                     # everything
uv run pytest tests/unit          # fast, no Docker
uv run pytest tests/integration   # repositories, API workflows, authentication
uv run pytest tests/conformance   # OpenAPI contract, Schemathesis, negative, security contract
uv run pytest -k duplicate        # tests whose name contains "duplicate"
uv run pytest -v                  # list every test name and its result
```

### How the tests are organized

| Folder | Boundary under test | Uses |
|---|---|---|
| `tests/unit/schemas/` | Pydantic rules: required fields, length and year limits, trimming, email, phone, ISBN, unknown fields | Plain Python |
| `tests/unit/services/` | Service decisions: missing records, relationship checks, uniqueness, blocked deletion. In-memory services run against a real `InMemoryStore`. Database services use **mockito test doubles** for the session factory and repositories, so they need no PostgreSQL. | Plain Python, mockito |
| `tests/unit/auth/`, `tests/unit/test_config.py` | Token-to-role mapping, 401/403 decisions, required and distinct token settings | Plain Python |
| `tests/integration/repositories/` | Real SQLAlchemy mappings: generated IDs, queries, unique constraints, the Member-to-Book foreign key (`ON DELETE RESTRICT`) | Testcontainers PostgreSQL |
| `tests/integration/routers/` | Complete HTTP workflows through `TestClient`. Each test runs **twice**, once per storage backend (`[database]` and `[memory]` in the output), plus persistence across an API restart | TestClient + both backends |
| `tests/integration/test_authentication_authorization_api.py` | Public vs. protected routes, 401 for missing/malformed/unknown tokens, 403 for member writes, admin writes, and unchanged data after denied requests | TestClient + PostgreSQL |
| `tests/conformance/` | `/openapi.json` is a valid OpenAPI document and publishes the designed operations, schemas, and statuses. Schemathesis checks generated GET requests. Negative tests confirm 404/409/422 outcomes **and** that each response matches its documented status and schema. | openapi-spec-validator, Schemathesis, jsonschema |

Shared fixtures live in `tests/conftest.py` (its docstring diagrams how they depend on each other). Request-body builders are in `tests/helpers.py`.

## Explore the API

- Swagger UI (interactive; use **Try it out** to send requests): <http://localhost:8000/docs>
- ReDoc (reference documentation): <http://localhost:8000/redoc>
- OpenAPI JSON (machine-readable contract): <http://localhost:8000/openapi.json>

The root (`/`), health (`/health`), and documentation endpoints are public. Every Book and Member operation requires a Bearer token.

### Authenticate in Swagger UI

1. Open <http://localhost:8000/docs> and click **Authorize** (top right).
2. Paste a token **without** the word `Bearer`, for example `admin-demo-token`, and click **Authorize**.
3. Protected operations (shown with a lock icon) now send `Authorization: Bearer admin-demo-token`. Use **Logout** and authorize with `member-demo-token` to see the read-only role receive `403` on writes.

### Request roles

| Role | Token setting | May read Books and Members | May create, replace, delete |
|---|---|---|---|
| member | `DEMO_MEMBER_TOKEN` | Yes | No (`403 Forbidden`) |
| administrator | `DEMO_ADMIN_TOKEN` | Yes | Yes |

These request roles describe **who is calling the API**. They are separate from the Library's stored Member records: a library Member is data, and the "member" role is a caller's permission level.

### Endpoints

| Method | URL | Operation | Access | Success status |
|---|---|---|---|---|
| `GET` | `/` | Read API introduction | Public | `200 OK` |
| `GET` | `/health` | Check API health | Public | `200 OK` |
| `GET` | `/members` | List all Members | Member or admin | `200 OK` |
| `GET` | `/members/{member_id}` | Get one Member | Member or admin | `200 OK` |
| `POST` | `/members` | Create a Member | Admin | `201 Created` |
| `PUT` | `/members/{member_id}` | Replace a Member | Admin | `200 OK` |
| `DELETE` | `/members/{member_id}` | Delete a Member | Admin | `204 No Content` |
| `GET` | `/members/{member_id}/books` | List a Member's Books | Member or admin | `200 OK` |
| `GET` | `/books` | List all Books | Member or admin | `200 OK` |
| `GET` | `/books/{book_id}` | Get one Book | Member or admin | `200 OK` |
| `POST` | `/books` | Create a Book | Admin | `201 Created` |
| `PUT` | `/books/{book_id}` | Replace a Book | Admin | `200 OK` |
| `DELETE` | `/books/{book_id}` | Delete a Book | Admin | `204 No Content` |

`PUT` replaces the whole resource, so the request must include every editable field.

### Error responses

| Status | When it is returned |
|---|---|
| `401 Unauthorized` | A protected operation was called with no `Authorization` header, a scheme other than `Bearer`, or an unknown token. The response includes the challenge header `WWW-Authenticate: Bearer`. |
| `403 Forbidden` | A valid **member** token was used for a create, replace, or delete. The role check runs before the request body is validated, and nothing is changed. |
| `404 Not Found` | The requested Book or Member does not exist, or a Book's `member_id` refers to a Member that does not exist. |
| `409 Conflict` | An ISBN, email, or membership ID is already used by another record, or a Member who still has Books is being deleted. |
| `422 Unprocessable Content` | The request body or path ID fails validation, for example a missing field, bad format, value out of range, or unknown field. |

Error bodies contain a short `detail` message, for example `{"detail": "Member not found"}`, documented in OpenAPI as the `ErrorResponse` schema. Raw database errors are never returned to clients.

## Example requests

The database starts empty. PostgreSQL generates IDs, so use the `id` values from your own responses; the examples below assume a fresh database.

### Bearer requests with curl

Writes need the administrator token:

```bash
curl -X POST http://localhost:8000/members \
  -H "Authorization: Bearer admin-demo-token" \
  -H "Content-Type: application/json" \
  -d '{"name": "Grace Hopper", "email": "grace@example.com", "membership_id": "LIB-0001", "phone": "555-987-6543"}'
```

Reads accept either token:

```bash
curl http://localhost:8000/members -H "Authorization: Bearer member-demo-token"
```

The member token cannot write. This returns `403` with `{"detail": "Administrator role required"}`:

```bash
curl -i -X DELETE http://localhost:8000/members/1 -H "Authorization: Bearer member-demo-token"
```

With no token, or an unknown one, the response is `401` with `{"detail": "Missing or invalid Bearer token"}` and the header `WWW-Authenticate: Bearer`:

```bash
curl -i http://localhost:8000/members
```

On Windows PowerShell, use `curl.exe` instead of `curl` and put each command on one line (PowerShell does not use `\` to continue lines). In the steps below, send each request with the administrator token, either through Swagger UI after **Authorize** or with the header shown above.

### 1. Create a Member — `POST /members`

```json
{
  "name": "Grace Hopper",
  "email": "grace@example.com",
  "membership_id": "LIB-0001",
  "phone": "555-987-6543"
}
```

Response `201 Created`:

```json
{
  "name": "Grace Hopper",
  "email": "grace@example.com",
  "membership_id": "LIB-0001",
  "phone": "555-987-6543",
  "id": 1
}
```

### 2. Create a Book borrowed by that Member — `POST /books`

```json
{
  "title": "Clean Code",
  "author": "Robert C. Martin",
  "isbn": "978-0-13-235088-4",
  "published_year": 2008,
  "member_id": 1
}
```

Response `201 Created` (hyphens are removed from the stored ISBN):

```json
{
  "title": "Clean Code",
  "author": "Robert C. Martin",
  "isbn": "9780132350884",
  "published_year": 2008,
  "member_id": 1,
  "id": 1
}
```

### 3. List that Member's Books — `GET /members/1/books`

Response `200 OK`:

```json
[
  {
    "title": "Clean Code",
    "author": "Robert C. Martin",
    "isbn": "9780132350884",
    "published_year": 2008,
    "member_id": 1,
    "id": 1
  }
]
```

### 4. Try to delete that Member — `DELETE /members/1`

Response `409 Conflict`:

```json
{ "detail": "Delete or reassign the member's books before deleting the member" }
```

To delete the Member, first delete the Book (`DELETE /books/1`) or reassign it to another Member by sending `PUT /books/1` with a different `member_id`.

### 5. Create a Book for a Member that does not exist — `POST /books`

Sending the Book body above with `"member_id": 99` returns `404 Not Found`:

```json
{ "detail": "Member not found" }
```

### 6. Reuse an email address — `POST /members`

Sending the Member body from step 1 again (or with `GRACE@example.com`) returns `409 Conflict`:

```json
{ "detail": "A member with this email already exists" }
```

### 7. Send invalid data — `POST /members`

```json
{
  "name": "   ",
  "email": "not-an-email",
  "membership_id": "LIB-0003",
  "phone": "5551234567"
}
```

Response `422 Unprocessable Content`. The `detail` list names each field that failed and the rule it broke. Nothing reaches the service or the database when validation fails.

## Validation rules

### Member

| Field | Rule |
|---|---|
| `name` | Required; 1–120 characters after leading and trailing whitespace is removed |
| `email` | Required; must be a valid email address; stored in lowercase; unique (case-insensitive) |
| `membership_id` | Required; 1–20 characters after trimming; unique |
| `phone` | Required; **must use the format `XXX-XXX-XXXX`** (10 digits separated by dashes, for example `555-123-4567`) |

### Book

| Field | Rule |
|---|---|
| `title` | Required; 1–200 characters after trimming |
| `author` | Required; 1–120 characters after trimming |
| `isbn` | Required; ISBN-10 (9 digits followed by a digit or `X`) or ISBN-13 (13 digits). Hyphens and spaces are removed before validation and storage. Must be unique. |
| `published_year` | Required; from 1450 to the current year |
| `member_id` | Required; a positive integer that identifies an existing Member |

### Rules for every resource

- `id` is generated by PostgreSQL (or by the in-memory service). It appears in responses and cannot be sent in a request body.
- Unknown fields in a request body are rejected.
- Path IDs must be integers from 1 to 2,147,483,647 (the PostgreSQL `INTEGER` maximum), so `/books/0`, `/books/abc`, and `/books/9999999999` return `422`. The same limit applies to a Book's `member_id`.

## How the application is organized

### Request flow

```text
HTTP request
    ↓
Auth          Bearer token → member/admin role → 401 or 403 if not allowed
    ↓
Router        validated input, service call, status code, HTTP error translation
    ↓
Service       Library business rules and the transaction boundary
    ↓
Repository    SQLAlchemy queries and writes
    ↓
ORM model     Python class ↔ PostgreSQL table
    ↓
PostgreSQL    durable Members and Books
```

- **Auth** (`app/auth/`) runs as FastAPI dependencies before the route handler. `get_current_user` reads the `Authorization` header and maps the token to a role through the typed settings. `require_admin` builds on it for write routes. Routes declare `CurrentUser` (any valid token) or `AdminUser` (administrator only). The Book and Member services never see tokens or roles: they stay focused on Library rules, which is also why they can be unit-tested without HTTP.
- **Schemas** (`app/schemas/`) are the API contract: Pydantic validates requests at the boundary and shapes responses.
- **Routers** (`app/routers/`) handle HTTP only. They receive a service through `Depends(...)`, call it, and translate application exceptions (`app/exceptions.py`) into `HTTPException` responses (`app/routers/http_errors.py`). They never open Sessions or write SQL.
- **Services** (`app/services/`) implement use cases such as "create a Book for an existing Member" and raise application exceptions, not HTTP errors. Each resource has an abstract contract (`base.py`) with a database implementation (`database.py`) and an in-memory implementation (`in_memory.py`).
- **Repositories** (`app/repositories/`) contain SQLAlchemy queries. They do not decide HTTP responses or business policy.
- **ORM models** (`app/models/`) define the `members` and `books` tables, their constraints, and the relationship between them.

### Sessions and transactions

`app/database/session.py` creates **one Engine** (which owns the connection pool) and **one session factory** at startup. Database services receive the factory, never a shared Session. Every service operation opens its own short-lived Session:

- Reads use `with self._session_factory() as session:`.
- Writes use `with self._session_factory.begin() as session:`. This commits when the block finishes and rolls back if any exception escapes, so a use case that needs several repository calls (for example, check the Member, check the ISBN, insert the Book) succeeds or fails as one unit.

### Database integrity

The services check existence and uniqueness first so they can return clear `404` and `409` responses. PostgreSQL enforces the same rules as a second line of defense:

| Rule | Database constraint |
|---|---|
| Unique email | `uq_members_email` |
| Unique membership ID | `uq_members_membership_id` |
| Unique ISBN | `uq_books_isbn` |
| A Book references an existing Member; a Member with Books cannot be deleted | `fk_books_member_id_members` (`ON DELETE RESTRICT`) |
| Required values | `NOT NULL` on every column |

If two requests race past a service check at the same moment, the constraint rejects the second write. `app/database/errors.py` recognizes the constraint by name and converts it to the same application exception, so the client still receives the normal `404` or `409` response and the transaction is rolled back.

### Backend selection and dependency injection

At startup, the `lifespan` function in `app/main.py` loads `Settings`, builds either the database or the in-memory services, and stores them on `app.state`. `app/dependencies.py` exposes them to routes:

```python
def create_book(data: BookCreate, service: BookService = Depends(get_book_service)) -> Book:
```

The route depends on the `BookService` contract, so switching `STORAGE_BACKEND` changes the implementation without changing any route code.

## Project structure

```text
.
├── app/
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── dependencies.py    # Bearer authentication, admin check, documented 401/403
│   │   └── users.py           # Request roles and the token → role mapping
│   ├── database/
│   │   ├── __init__.py
│   │   ├── errors.py          # Maps constraint violations to application exceptions
│   │   └── session.py         # Engine and session factory, created once at startup
│   ├── models/
│   │   ├── __init__.py        # Registers every ORM model with SQLAlchemy
│   │   ├── base.py            # DeclarativeBase shared by all models
│   │   ├── book.py            # books table, ISBN unique constraint, foreign key
│   │   └── member.py          # members table, email and membership ID constraints
│   ├── repositories/
│   │   ├── __init__.py
│   │   ├── books.py           # SQLAlchemy queries for Books
│   │   └── members.py         # SQLAlchemy queries for Members
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── books.py           # /books endpoints
│   │   ├── http_errors.py     # Application outcome → HTTPException
│   │   └── members.py         # /members endpoints and a Member's Books
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── books.py           # BookCreate, BookUpdate, BookResponse
│   │   ├── errors.py          # ErrorResponse, the documented {"detail": ...} body
│   │   ├── ids.py             # MAX_ID, the largest ID PostgreSQL INTEGER can store
│   │   └── members.py         # MemberCreate, MemberUpdate, MemberResponse
│   ├── services/
│   │   ├── __init__.py
│   │   ├── books/
│   │   │   ├── __init__.py
│   │   │   ├── base.py        # BookService contract
│   │   │   ├── database.py    # PostgreSQL implementation
│   │   │   └── in_memory.py   # Process-local implementation
│   │   ├── members/
│   │   │   ├── __init__.py
│   │   │   ├── base.py        # MemberService contract
│   │   │   ├── database.py    # PostgreSQL implementation
│   │   │   └── in_memory.py   # Process-local implementation
│   │   └── in_memory_store.py # Lists and lock shared by the in-memory services
│   ├── __init__.py
│   ├── config.py              # Typed Settings (storage, database, role tokens)
│   ├── dependencies.py        # FastAPI dependencies for settings and the selected services
│   ├── exceptions.py          # Application exceptions raised by services
│   └── main.py                # App creation, startup wiring, router registration
├── scripts/
│   └── setup_database.sql     # Creates the local role and database
├── tests/
│   ├── conformance/
│   │   ├── test_authentication_authorization_contract.py  # Published security scheme and 401/403
│   │   ├── test_negative_requests.py                      # 404/409/422 outcomes, unchanged data
│   │   └── test_openapi_contract.py                       # Document validity, schemas, Schemathesis
│   ├── integration/
│   │   ├── repositories/
│   │   │   ├── test_books.py          # Book queries, unique ISBN, foreign key
│   │   │   └── test_members.py        # Member queries, unique email and membership ID
│   │   ├── routers/
│   │   │   ├── test_books.py          # Book workflows on both backends
│   │   │   ├── test_members.py        # Member workflows and related Books on both backends
│   │   │   └── test_persistence.py    # Data across an API restart, per backend
│   │   └── test_authentication_authorization_api.py  # Public/protected, 401, 403, admin writes
│   ├── unit/
│   │   ├── auth/
│   │   │   ├── test_dependencies.py   # get_current_user and require_admin
│   │   │   └── test_users.py          # Token → role mapping
│   │   ├── schemas/
│   │   │   ├── test_books.py
│   │   │   └── test_members.py
│   │   ├── services/
│   │   │   ├── books/
│   │   │   │   ├── test_database.py   # Mocked repositories and session factory
│   │   │   │   └── test_in_memory.py
│   │   │   ├── members/
│   │   │   │   ├── test_database.py
│   │   │   │   └── test_in_memory.py
│   │   │   └── conftest.py            # fake_database fixture (mockito doubles)
│   │   └── test_config.py             # Settings validation
│   ├── conftest.py            # Testcontainers, database reset, TestClients, tokens
│   ├── contract.py            # assert_conforms: response vs. /openapi.json
│   ├── fakes.py               # FakeDatabase and IntegrityError builder for unit tests
│   └── helpers.py             # Request-body builders and API helpers
├── .env.example               # Documented settings with safe local defaults
├── .gitignore
├── .python-version
├── pyproject.toml
├── README.md
└── uv.lock
```
