# PostgreSQL Auth Storage — Design Spec

## Motivation

Replace the in-memory `_users` dict in `api/v1/auth.py` with a proper PostgreSQL-backed user store, enabling persistent user data across restarts and paving the way for future multi-user features.

## Scope

- Single table `users` with username, password_hash, role, timestamps
- Asyncpg connection pool wrapper (`PostgresClient`)
- Repository layer (`UserRepo`)
- Integration into existing lifespan/dependency injection pattern
- Auto-seed admin user on first start
- **No migration framework** — schema created via `CREATE TABLE IF NOT EXISTS` on startup

## Architecture

```
api/v1/auth.py  ──→  storage/user_repo.py  ──→  storage/postgres_client.py  ──→ asyncpg ──→ Postgres
```

## Components

### 1. `PostgresClient` (`storage/postgres_client.py`)

Connection-pool wrapper following the `RedisClient`/`Neo4jClient` pattern:

```python
class PostgresClient:
    @classmethod
    async def create(cls) -> "PostgresClient"
    async def execute(self, sql: str, *args) -> str          # INSERT/UPDATE/DELETE
    async def fetchrow(self, sql: str, *args) -> dict | None # single row
    async def fetch(self, sql: str, *args) -> list[dict]     # multiple rows
    async def close(self) -> None
```

- Uses `asyncpg.create_pool()` with settings from `Settings`
- `create()` runs `_init_schema()` to ensure table exists
- Connections use `type` codec for Postgres-compatible types

### 2. `UserRepo` (`storage/user_repo.py`)

```python
class UserRepo:
    def __init__(self, pg: PostgresClient) -> None
    async def get_user(self, username: str) -> dict | None
    async def create_user(self, username: str, password_hash: str, role: str = "user") -> dict
    async def update_password_hash(self, username: str, password_hash: str) -> None
    async def user_exists(self, username: str) -> bool
```

- All methods are thin wrappers over `PostgresClient` SQL calls
- Returns raw dicts (no ORM models — keeping it simple)

### 3. Schema

```sql
CREATE TABLE IF NOT EXISTS users (
    username       VARCHAR(255) PRIMARY KEY,
    password_hash  VARCHAR(255) NOT NULL,
    role           VARCHAR(50) NOT NULL DEFAULT 'user',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 4. Changes to existing files

**`main.py`** — lifespan:
- `postgres = await PostgresClient.create()` after neo4j/redis init
- `await app.state.postgres.close()` in shutdown
- Auto-seed admin user: if `ADMIN_USERNAME`/`ADMIN_PASSWORD` configured and table empty, insert

**`api/deps.py`** — new dependencies:
```python
def get_postgres(request: Request) -> PostgresClient
def get_user_repo(pg: PostgresClient = Depends(get_postgres)) -> UserRepo
```

**`api/v1/auth.py`** — replace `_users` dict:
- Delete global `_users` dict
- `login`/`register`/`refresh` accept `UserRepo = Depends(get_user_repo)` instead
- `register` uses `user_repo.create_user()`, returns username/exists conflict
- `login` uses `user_repo.get_user()` for credential check
- `refresh` still reads role via `user_repo.get_user()`

**Dependencies** — add to `pyproject.toml`:
```toml
asyncpg = "^0.30"
```

## Config

Existing `POSTGRES_*` settings already in `Settings`. Add:
- `ADMIN_USERNAME: str = "admin"`  (already implied in code)
- `ADMIN_PASSWORD: str = "admin123"` (default for first-run seed; production should override)

## Error Handling

- Connection failure → `RuntimeError` on startup (same pattern as RedisClient)
- Query timeout → asyncpg default timeout (configurable via settings)
- Duplicate insert → integrity error caught in `create_user`, raised as `InvalidInput`
- User not found → return `None` (caller handles 404)

## Edge Cases

- **Empty table**: seed script runs silently, first registered user via API becomes regular user
- **Concurrent register**: unique constraint handles race (try INSERT, catch unique violation)
- **Special chars in username**: parameterized queries prevent injection
- **Startup without Postgres**: currently blocks startup (same as Redis/Neo4j); future: grace mode

## Non-goals

- Alembic migrations / schema versioning (not needed for single table)
- Password hashing upgrade (stays SHA256 per user preference)
- User delete / role management endpoints (future work)
- Connection pooling tuning (defaults adequate for expected load)
