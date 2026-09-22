# Library Management System API

The Library Management System API is a backend that library staff use to manage **Members** and the **Books** they borrow. Staff can create, view, update, and delete both resources. Each Book is borrowed by exactly one existing Member, and a Member can borrow many Books.

This is Assignment 1 for SDEV 3310. It covers REST design, CRUD operations, Pydantic validation, and the OpenAPI contract. Data is kept in memory for now. Assignment 2 will replace it with SQLAlchemy and a relational database.

## Requirements

- [uv](https://docs.astral.sh/uv/)

`uv` manages the Python version, the virtual environment, and the project dependencies.

### Install uv

macOS and Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Windows PowerShell:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Restart your terminal, then check the installation:

```bash
uv --version
```

### Set up the project

Clone the repository and switch to the assignment branch:

```bash
git clone <repository-url>
cd <repository-folder>
git checkout assignment-1
```

From the repository root, run:

```bash
uv sync
```

`uv sync` downloads Python 3.13 if it is missing, creates `.venv/`, and installs the exact dependency versions recorded in `uv.lock`.

## Run the API

```bash
uv run uvicorn app.main:app --reload
```

- `app.main:app` tells Uvicorn to load the `app` object from `app/main.py`.
- `--reload` restarts the server when source code changes.

The server runs at `http://localhost:8000`.

## Explore the API

- Swagger UI (interactive; use **Try it out** to send requests): <http://localhost:8000/docs>
- ReDoc (reference documentation): <http://localhost:8000/redoc>
- OpenAPI JSON (machine-readable contract): <http://localhost:8000/openapi.json>

### Endpoints

| Method | URL | Operation | Success status |
|---|---|---|---|
| `GET` | `/` | Read API introduction | `200 OK` |
| `GET` | `/health` | Check API health | `200 OK` |
| `GET` | `/members` | List all Members | `200 OK` |
| `GET` | `/members/{member_id}` | Get one Member | `200 OK` |
| `POST` | `/members` | Create a Member | `201 Created` |
| `PUT` | `/members/{member_id}` | Replace a Member | `200 OK` |
| `DELETE` | `/members/{member_id}` | Delete a Member | `204 No Content` |
| `GET` | `/members/{member_id}/books` | List a Member's Books | `200 OK` |
| `GET` | `/books` | List all Books | `200 OK` |
| `GET` | `/books/{book_id}` | Get one Book | `200 OK` |
| `POST` | `/books` | Create a Book | `201 Created` |
| `PUT` | `/books/{book_id}` | Replace a Book | `200 OK` |
| `DELETE` | `/books/{book_id}` | Delete a Book | `204 No Content` |

`PUT` replaces the whole resource, so the request must include every editable field.

### Error responses

| Status | When it is returned |
|---|---|
| `404 Not Found` | The requested Book or Member does not exist, or a Book's `member_id` refers to a Member that does not exist. |
| `409 Conflict` | An ISBN, email, or membership ID is already used by another record, or a Member who still has Books is being deleted. |
| `422 Unprocessable Content` | The request body or path ID fails validation, for example a missing field, bad format, value out of range, or unknown field. |

## Example requests

The application starts with one sample Member (ID `1`) and one sample Book (ID `1`). The examples below create a new Member and then a Book borrowed by that Member.

### 1. Create a Member — `POST /members`

```json
{
  "name": "Grace Hopper",
  "email": "grace@example.com",
  "membership_id": "LIB-0002",
  "phone": "555-987-6543"
}
```

Response `201 Created`:

```json
{
  "name": "Grace Hopper",
  "email": "grace@example.com",
  "membership_id": "LIB-0002",
  "phone": "555-987-6543",
  "id": 2
}
```

### 2. Create a Book borrowed by that Member — `POST /books`

```json
{
  "title": "Clean Code",
  "author": "Robert C. Martin",
  "isbn": "978-0-13-235088-4",
  "published_year": 2008,
  "member_id": 2
}
```

Response `201 Created` (hyphens are removed from the stored ISBN):

```json
{
  "title": "Clean Code",
  "author": "Robert C. Martin",
  "isbn": "9780132350884",
  "published_year": 2008,
  "member_id": 2,
  "id": 2
}
```

### 3. List that Member's Books — `GET /members/2/books`

Response `200 OK`:

```json
[
  {
    "title": "Clean Code",
    "author": "Robert C. Martin",
    "isbn": "9780132350884",
    "published_year": 2008,
    "member_id": 2,
    "id": 2
  }
]
```

### 4. Try to delete that Member — `DELETE /members/2`

Response `409 Conflict`:

```json
{ "detail": "Delete or reassign the member's books before deleting the member" }
```

To delete the Member, first delete the Book (`DELETE /books/2`) or reassign it by sending `PUT /books/2` with a different `member_id`.

### 5. Create a Book for a Member that does not exist — `POST /books`

Sending the Book body above with `"member_id": 99` returns `404 Not Found`:

```json
{ "detail": "Member not found" }
```

### 6. Send invalid data — `POST /members`

```json
{
  "name": "   ",
  "email": "not-an-email",
  "membership_id": "LIB-0003",
  "phone": "5551234567"
}
```

Response `422 Unprocessable Content`. The `detail` list names each field that failed and the rule it broke. The route function does not run when validation fails.

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

- `id` is generated by the server. It appears in responses and cannot be sent in a request body.
- Unknown fields in a request body are rejected.
- Path IDs must be positive integers, so `/books/0` returns `422`.

## Temporary data

Members and Books are stored in Python lists while the server runs. All changes are lost when the server restarts. This limitation is intentional for Assignment 1.

## Project structure

```text
.
├── app/
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── books.py        # /books endpoints and ISBN uniqueness check
│   │   └── members.py      # /members endpoints, uniqueness checks, a Member's Books
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── books.py        # BookCreate, BookUpdate, BookResponse
│   │   └── members.py      # MemberCreate, MemberUpdate, MemberResponse
│   ├── __init__.py
│   ├── main.py             # FastAPI app, OpenAPI metadata, router registration
│   └── storage.py          # In-memory lists with sample data
├── .gitignore
├── .python-version
├── pyproject.toml
├── README.md
└── uv.lock
```

The project is organized in layers:

- **Schemas** (`app/schemas/`) define the data contract: what a valid request looks like and what a response contains.
- **Routers** (`app/routers/`) handle HTTP concerns and business rules that need other records, such as uniqueness, whether a referenced Member exists, and blocking deletion.
- **Storage** (`app/storage.py`) holds the data. Keeping it in its own module makes it easier to replace with a database in Assignment 2.
