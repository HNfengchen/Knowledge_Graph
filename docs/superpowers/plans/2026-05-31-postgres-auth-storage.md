# PostgreSQL Auth Storage — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the in-memory `_users` dict in `api/v1/auth.py` with a PostgreSQL-backed `UserRepo`.

**Architecture:** `PostgresClient` wraps an asyncpg pool (same pattern as `RedisClient`/`Neo4jClient`). `UserRepo` provides thin CRUD methods over it. Auth endpoints switch from `_users` dict to `UserRepo` dependency injection.

**Tech Stack:** asyncpg, FastAPI Depends, SHA256 password hashing

---

### Task 1: Add asyncpg dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Add asyncpg to dependencies**

```toml
# pyproject.toml
dependencies = [
    ...
    "asyncpg>=0.30,<1.0",
]
```

- [ ] **Install and verify**

```bash
pip install asyncpg
python -c "import asyncpg; print(asyncpg.__version__)"
```

- [ ] **Commit**

```bash
git add pyproject.toml
git commit -m "deps: add asyncpg for PostgreSQL support"
```

---

### Task 2: Create PostgresClient

**Files:**
- Create: `src/kg_system/storage/postgres_client.py`
- Create: `tests/unit/test_storage_postgres_client.py`

- [ ] **Write PostgresClient**

```python
# src/kg_system/storage/postgres_client.py
from __future__ import annotations

import asyncpg

from kg_system.core.config import get_settings
from kg_system.core.logging import get_logger

log = get_logger(__name__)

_INIT_SQL = """
CREATE TABLE IF NOT EXISTS users (
    username       VARCHAR(255) PRIMARY KEY,
    password_hash  VARCHAR(255) NOT NULL,
    role           VARCHAR(50) NOT NULL DEFAULT 'user',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


class PostgresClient:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    @classmethod
    async def create(cls) -> PostgresClient:
        s = get_settings()
        pool = await asyncpg.create_pool(
            host=s.POSTGRES_HOST,
            port=s.POSTGRES_PORT,
            user=s.POSTGRES_USER,
            password=s.POSTGRES_PASSWORD,
            database=s.POSTGRES_DATABASE,
            min_size=1,
            max_size=s.POSTGRES_POOL_SIZE,
        )
        async with pool.acquire() as conn:
            await conn.execute(_INIT_SQL)
        log.info("pg_connected", host=s.POSTGRES_HOST, port=s.POSTGRES_PORT)
        return cls(pool)

    async def execute(self, sql: str, *args: object) -> str:
        async with self._pool.acquire() as conn:
            return await conn.execute(sql, *args)

    async def fetchrow(self, sql: str, *args: object) -> dict | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(sql, *args)
            return dict(row) if row else None

    async def fetch(self, sql: str, *args: object) -> list[dict]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, *args)
            return [dict(r) for r in rows]

    async def close(self) -> None:
        await self._pool.close()
        log.info("pg_disconnected")
```

- [ ] **Commit**

```bash
git add src/kg_system/storage/postgres_client.py
git commit -m "feat(storage): add PostgresClient with asyncpg pool"
```

---

### Task 3: Create UserRepo

**Files:**
- Create: `src/kg_system/storage/user_repo.py`
- Create: `tests/unit/test_storage_user_repo.py`

- [ ] **Write UserRepo**

```python
# src/kg_system/storage/user_repo.py
from __future__ import annotations

from kg_system.core.logging import get_logger
from kg_system.storage.postgres_client import PostgresClient

log = get_logger(__name__)


class UserRepo:
    def __init__(self, pg: PostgresClient) -> None:
        self._pg = pg

    async def get_user(self, username: str) -> dict | None:
        return await self._pg.fetchrow(
            "SELECT username, password_hash, role, created_at, updated_at "
            "FROM users WHERE username = $1",
            username,
        )

    async def create_user(self, username: str, password_hash: str, role: str = "user") -> dict:
        await self._pg.execute(
            "INSERT INTO users (username, password_hash, role) VALUES ($1, $2, $3)",
            username,
            password_hash,
            role,
        )
        user = await self.get_user(username)
        assert user is not None
        return user

    async def update_password_hash(self, username: str, password_hash: str) -> None:
        await self._pg.execute(
            "UPDATE users SET password_hash = $1, updated_at = NOW() WHERE username = $2",
            password_hash,
            username,
        )

    async def user_exists(self, username: str) -> bool:
        row = await self._pg.fetchrow(
            "SELECT 1 FROM users WHERE username = $1", username
        )
        return row is not None
```

- [ ] **Commit**

```bash
git add src/kg_system/storage/user_repo.py
git commit -m "feat(storage): add UserRepo for user CRUD"
```

---

### Task 4: Register PostgresClient in application lifespan

**Files:**
- Modify: `src/kg_system/main.py`
- Modify: `src/kg_system/api/deps.py`

- [ ] **Add postgres to lifespan in main.py**

```python
# 在 lifespan startup 的 try 块中（neo4j/redis 初始化之后）：
postgres = await PostgresClient.create()
app.state.postgres = postgres

# 在 shutdown 的 finally 块中：
if hasattr(app.state, "postgres") and app.state.postgres:
    await app.state.postgres.close()

# Seed default admin if configured（同样在 startup try 块中，紧跟 postgres 创建之后）：
s = get_settings()
if s.ADMIN_USERNAME and s.ADMIN_PASSWORD:
    from kg_system.storage.user_repo import UserRepo
    repo = UserRepo(postgres)
    admin = await repo.get_user(s.ADMIN_USERNAME)
    if not admin:
        import hashlib
        pw_hash = hashlib.sha256(s.ADMIN_PASSWORD.encode()).hexdigest()
        await repo.create_user(s.ADMIN_USERNAME, pw_hash, role="admin")
        log.info("admin_seeded", username=s.ADMIN_USERNAME)
```python
# Seed default admin if configured
s = get_settings()
if s.ADMIN_USERNAME and s.ADMIN_PASSWORD:
    from kg_system.storage.user_repo import UserRepo
    repo = UserRepo(postgres)
    admin = await repo.get_user(s.ADMIN_USERNAME)
    if not admin:
        import hashlib
        pw_hash = hashlib.sha256(s.ADMIN_PASSWORD.encode()).hexdigest()
        await repo.create_user(s.ADMIN_USERNAME, pw_hash, role="admin")
        log.info("admin_seeded", username=s.ADMIN_USERNAME)
```

- [ ] **Add get_postgres and get_user_repo deps in api/deps.py**

```python
# 在 api/deps.py 末尾添加：
from kg_system.storage.postgres_client import PostgresClient
from kg_system.storage.user_repo import UserRepo

def get_postgres(request: Request) -> PostgresClient:
    return request.app.state.postgres

def get_user_repo(pg: PostgresClient = Depends(get_postgres)) -> UserRepo:
    return UserRepo(pg)
```

- [ ] **Commit**

```bash
git add src/kg_system/main.py src/kg_system/api/deps.py
git commit -m "feat: register PostgresClient in lifespan and add DI deps"
```

---

### Task 5: Add ADMIN_USERNAME / ADMIN_PASSWORD to config

**Files:**
- Modify: `src/kg_system/core/config.py`

- [ ] **Add config fields**

After `EXTERNAL_API_IP_WHITELIST` line, add:
```python
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = ""
```

- [ ] **Commit**

```bash
git add src/kg_system/core/config.py
git commit -m "feat(config): add ADMIN_USERNAME and ADMIN_PASSWORD settings"
```

---

### Task 6: Rewrite auth.py to use UserRepo instead of _users dict

**Files:**
- Modify: `src/kg_system/api/v1/auth.py`

- [ ] **Full rewrite of auth.py**

```python
from __future__ import annotations

import hashlib
import time
import uuid

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from kg_system.api.deps import get_redis, get_user_repo, require_user
from kg_system.auth.jwt import create_access_token, create_refresh_token, decode_token
from kg_system.core.config import get_settings
from kg_system.core.exceptions import AuthError, RateLimitError
from kg_system.core.logging import get_logger
from kg_system.core.models import ApiResponse
from kg_system.storage.redis_client import RedisClient
from kg_system.storage.user_repo import UserRepo

log = get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


class LoginReq(BaseModel):
    username: str
    password: str


class TokenReq(BaseModel):
    refresh_token: str


class LogoutReq(BaseModel):
    jti: str = ""


async def _check_login_rate_limit(redis: RedisClient, ip: str) -> None:
    minute = int(time.time()) // 60
    key = f"{get_settings().REDIS_KEY_PREFIX}auth:fail:{ip}:{minute}"
    r = redis.get_client()
    try:
        count = await r.get(key)
        if count and int(count) >= 5:
            raise RateLimitError("too many login attempts, try again later")
    finally:
        await r.close()


@router.post("/login", response_model=ApiResponse[dict])
async def login(
    body: LoginReq,
    request: Request,
    redis: RedisClient = Depends(get_redis),
    users: UserRepo = Depends(get_user_repo),
):
    ip = request.client.host if request.client else "unknown"
    await _check_login_rate_limit(redis, ip)

    user = await users.get_user(body.username)
    if not user:
        raise AuthError("invalid username or password")

    pw_hash = hashlib.sha256(body.password.encode()).hexdigest()
    if user["password_hash"] != pw_hash:
        r = redis.get_client()
        try:
            minute = int(time.time()) // 60
            key = f"{get_settings().REDIS_KEY_PREFIX}auth:fail:{ip}:{minute}"
            await r.incr(key)
            await r.expire(key, 60)
        finally:
            await r.close()
        raise AuthError("invalid username or password")

    access = create_access_token(body.username, role=user["role"])
    refresh = create_refresh_token(body.username)
    s = get_settings()

    return ApiResponse(
        data={
            "access_token": access,
            "refresh_token": refresh,
            "expires_in": s.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }
    )


@router.post("/refresh", response_model=ApiResponse[dict])
async def refresh_token(
    body: TokenReq,
    redis: RedisClient = Depends(get_redis),
    users: UserRepo = Depends(get_user_repo),
):
    payload = decode_token(body.refresh_token)

    if payload.get("type") != "refresh":
        raise AuthError("invalid refresh token")

    jti = payload.get("jti", "")
    r = redis.get_client()
    try:
        revoked = await r.get(f"{get_settings().REDIS_KEY_PREFIX}auth:revoked:{jti}")
        if revoked:
            raise AuthError("token revoked")
        await r.setex(f"{get_settings().REDIS_KEY_PREFIX}auth:revoked:{jti}", 604800, "1")
    finally:
        await r.close()

    sub = payload.get("sub", "")
    user = await users.get_user(sub)
    role = user["role"] if user else "user"
    access = create_access_token(sub, role=role)
    new_refresh = create_refresh_token(sub)

    return ApiResponse(
        data={
            "access_token": access,
            "refresh_token": new_refresh,
            "expires_in": 900,
        }
    )


@router.post("/logout", response_model=ApiResponse[dict])
async def logout(
    body: LogoutReq,
    redis: RedisClient = Depends(get_redis),
    user=Depends(require_user),
):
    if body.jti:
        r = redis.get_client()
        try:
            await r.setex(f"{get_settings().REDIS_KEY_PREFIX}auth:revoked:{body.jti}", 604800, "1")
        finally:
            await r.close()

    return ApiResponse(data={"message": "logged out"})


@router.post("/register", response_model=ApiResponse[dict])
async def register(
    body: LoginReq,
    users: UserRepo = Depends(get_user_repo),
):
    if len(body.password) < 6:
        raise AuthError("password too short, minimum 6 characters")

    exists = await users.user_exists(body.username)
    if exists:
        raise AuthError("username already exists")

    pw_hash = hashlib.sha256(body.password.encode()).hexdigest()
    await users.create_user(body.username, pw_hash, role="user")
    return ApiResponse(data={"message": "user created"})
```

- [ ] **Commit**

```bash
git add src/kg_system/api/v1/auth.py
git commit -m "feat(auth): replace _users dict with UserRepo"
```

---

### Task 7: Write unit tests for PostgresClient

**Files:**
- Create: `tests/unit/test_storage_postgres_client.py`

- [ ] **Write test file**

```python
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kg_system.storage.postgres_client import PostgresClient


@pytest.mark.unit
class TestPostgresClient:
    async def test_create_inits_schema(self):
        fake_pool = AsyncMock()
        fake_conn = AsyncMock()
        fake_pool.acquire = MagicMock()
        fake_pool.acquire.return_value.__aenter__.return_value = fake_conn

        with patch("asyncpg.create_pool", AsyncMock(return_value=fake_pool)):
            with patch("kg_system.storage.postgres_client._INIT_SQL", "CREATE TABLE ..."):
                client = await PostgresClient.create()

        assert client._pool is fake_pool
        fake_conn.execute.assert_called_once()

    async def test_execute(self):
        fake_pool = AsyncMock()
        fake_conn = AsyncMock()
        fake_pool.acquire = MagicMock()
        fake_pool.acquire.return_value.__aenter__.return_value = fake_conn
        fake_conn.execute.return_value = "INSERT 0 1"

        client = PostgresClient(fake_pool)
        result = await client.execute("INSERT INTO t VALUES($1)", "v")

        assert result == "INSERT 0 1"
        fake_conn.execute.assert_called_once_with("INSERT INTO t VALUES($1)", "v")

    async def test_fetchrow_returns_dict(self):
        fake_pool = AsyncMock()
        fake_conn = AsyncMock()
        fake_pool.acquire = MagicMock()
        fake_pool.acquire.return_value.__aenter__.return_value = fake_conn

        class FakeRow(dict):
            pass
        fake_conn.fetchrow.return_value = FakeRow({"username": "alice"})

        client = PostgresClient(fake_pool)
        result = await client.fetchrow("SELECT * FROM users WHERE username=$1", "alice")

        assert result == {"username": "alice"}

    async def test_fetchrow_returns_none(self):
        fake_pool = AsyncMock()
        fake_conn = AsyncMock()
        fake_pool.acquire = MagicMock()
        fake_pool.acquire.return_value.__aenter__.return_value = fake_conn
        fake_conn.fetchrow.return_value = None

        client = PostgresClient(fake_pool)
        result = await client.fetchrow("SELECT * FROM users WHERE username=$1", "nobody")

        assert result is None

    async def test_fetch_returns_list_of_dicts(self):
        fake_pool = AsyncMock()
        fake_conn = AsyncMock()
        fake_pool.acquire = MagicMock()
        fake_pool.acquire.return_value.__aenter__.return_value = fake_conn

        class FakeRow(dict):
            pass
        fake_conn.fetch.return_value = [FakeRow({"username": "a"}), FakeRow({"username": "b"})]

        client = PostgresClient(fake_pool)
        result = await client.fetch("SELECT * FROM users")

        assert result == [{"username": "a"}, {"username": "b"}]

    async def test_close(self):
        fake_pool = AsyncMock()
        client = PostgresClient(fake_pool)
        await client.close()
        fake_pool.close.assert_called_once()
```

- [ ] **Run tests**

```bash
python -m pytest tests/unit/test_storage_postgres_client.py -m unit -v
```

Expected: 6 passed

- [ ] **Commit**

```bash
git add tests/unit/test_storage_postgres_client.py
git commit -m "test: add PostgresClient unit tests"
```

---

### Task 8: Write unit tests for UserRepo

**Files:**
- Create: `tests/unit/test_storage_user_repo.py`

- [ ] **Write test file**

```python
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from kg_system.storage.user_repo import UserRepo


@pytest.fixture
def fake_pg():
    pg = AsyncMock()
    pg.execute = AsyncMock()
    pg.fetchrow = AsyncMock()
    pg.fetch = AsyncMock()
    return pg


@pytest.fixture
def repo(fake_pg):
    return UserRepo(fake_pg)


@pytest.mark.unit
class TestUserRepo:
    async def test_get_user_found(self, repo, fake_pg):
        fake_pg.fetchrow.return_value = {
            "username": "alice",
            "password_hash": "abc123",
            "role": "user",
            "created_at": "2025-01-01",
            "updated_at": "2025-01-01",
        }
        user = await repo.get_user("alice")
        assert user["username"] == "alice"
        fake_pg.fetchrow.assert_called_once()

    async def test_get_user_not_found(self, repo, fake_pg):
        fake_pg.fetchrow.return_value = None
        user = await repo.get_user("nobody")
        assert user is None

    async def test_create_user(self, repo, fake_pg):
        fake_pg.fetchrow.side_effect = [
            None,  # first call (in execute path)
            {"username": "bob", "password_hash": "xyz", "role": "user", "created_at": "", "updated_at": ""},  # get_user
        ]
        user = await repo.create_user("bob", "xyz", role="user")
        assert user["username"] == "bob"
        assert fake_pg.execute.call_count == 1

    async def test_user_exists_true(self, repo, fake_pg):
        fake_pg.fetchrow.return_value = {"1": 1}
        assert await repo.user_exists("alice") is True

    async def test_user_exists_false(self, repo, fake_pg):
        fake_pg.fetchrow.return_value = None
        assert await repo.user_exists("alice") is False

    async def test_update_password_hash(self, repo, fake_pg):
        await repo.update_password_hash("alice", "newhash")
        fake_pg.execute.assert_called_once()
        args = fake_pg.execute.call_args[0]
        assert "UPDATE" in args[0]
        assert args[1] == "newhash"
        assert args[2] == "alice"
```

- [ ] **Run tests**

```bash
python -m pytest tests/unit/test_storage_user_repo.py -m unit -v
```

Expected: 6 passed

- [ ] **Commit**

```bash
git add tests/unit/test_storage_user_repo.py
git commit -m "test: add UserRepo unit tests"
```

---

### Task 9: Update auth tests for UserRepo DI

**Files:**
- Modify: `tests/unit/test_api_auth.py` (create if not exists, or `tests/unit/test_api_v1_auth.py`)

- [ ] **Check existing auth test structure**

```bash
ls tests/unit/test_api* tests/unit/test_auth* 2>/dev/null || echo "no auth tests yet"
```

- [ ] **Write auth endpoint integration tests** (using mocked UserRepo)

```python
from __future__ import annotations

import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient, ASGITransport
from asgi_lifespan import LifespanManager

from kg_system.core.config import get_settings
from kg_system.main import create_app


@pytest.fixture
def app_with_fake_user_repo():
    """Override UserRepo dependency with fake."""
    from kg_system.storage.user_repo import UserRepo

    fake_repo = AsyncMock(spec=UserRepo)

    app = create_app()
    app.dependency_overrides = {}

    async def override_get_user_repo():
        return fake_repo

    # We need the DI function, import it
    from kg_system.api.deps import get_user_repo
    app.dependency_overrides[get_user_repo] = override_get_user_repo

    return app, fake_repo


@pytest.mark.unit
class TestAuthLogin:
    async def test_login_success(self):
        from kg_system.api.deps import get_user_repo

        fake_repo = AsyncMock()
        fake_repo.get_user.return_value = {
            "username": "alice",
            "password_hash": hashlib.sha256("secret".encode()).hexdigest(),
            "role": "user",
        }

        app = create_app()
        app.dependency_overrides[get_user_repo] = lambda: fake_repo

        async with LifespanManager(app):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/v1/auth/login",
                    json={"username": "alice", "password": "secret"},
                )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "access_token" in data["data"]

    async def test_login_wrong_password(self):
        from kg_system.api.deps import get_user_repo

        fake_repo = AsyncMock()
        fake_repo.get_user.return_value = {
            "username": "alice",
            "password_hash": hashlib.sha256("secret".encode()).hexdigest(),
            "role": "user",
        }

        app = create_app()
        app.dependency_overrides[get_user_repo] = lambda: fake_repo

        async with LifespanManager(app):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/v1/auth/login",
                    json={"username": "alice", "password": "wrong"},
                )
        assert resp.status_code == 401
        assert resp.json()["success"] is False

    async def test_register_success(self):
        from kg_system.api.deps import get_user_repo

        fake_repo = AsyncMock()
        fake_repo.user_exists.return_value = False
        fake_repo.create_user.return_value = {
            "username": "bob",
            "password_hash": "xxx",
            "role": "user",
        }

        app = create_app()
        app.dependency_overrides[get_user_repo] = lambda: fake_repo

        async with LifespanManager(app):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/v1/auth/register",
                    json={"username": "bob", "password": "pass123"},
                )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    async def test_register_duplicate(self):
        from kg_system.api.deps import get_user_repo

        fake_repo = AsyncMock()
        fake_repo.user_exists.return_value = True

        app = create_app()
        app.dependency_overrides[get_user_repo] = lambda: fake_repo

        async with LifespanManager(app):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/v1/auth/register",
                    json={"username": "bob", "password": "pass123"},
                )
        assert resp.status_code == 401
        assert resp.json()["success"] is False

    async def test_register_password_too_short(self):
        from kg_system.api.deps import get_user_repo

        fake_repo = AsyncMock()
        fake_repo.user_exists.return_value = False

        app = create_app()
        app.dependency_overrides[get_user_repo] = lambda: fake_repo

        async with LifespanManager(app):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/v1/auth/register",
                    json={"username": "bob", "password": "12345"},
                )
        assert resp.status_code == 401
        assert "6" in resp.json()["message"]
```

Actually, let me check if `test/unit/test_api_auth.py` exists first:

```bash
ls tests/unit/test_api_auth* 2>/dev/null || echo "not found"
```

If not found, write the full test file above. If found, update it.

- [ ] **Commit**

```bash
git add tests/unit/test_api_auth.py
git commit -m "test: add auth endpoint integration tests with mocked UserRepo"
```

---

### Task 10: Final integration run

**Files:**
- Run all tests

- [ ] **Run all unit tests**

```bash
python -m pytest tests/ -m unit --no-header -v 2>&1
```

Expected: all existing 62 tests + new tests pass (approximately 74+ tests)

- [ ] **Verify app imports cleanly**

```bash
python -c "from kg_system.main import create_app; print('OK')"
```
