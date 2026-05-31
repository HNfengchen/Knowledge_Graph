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
        if user is None:
            from kg_system.core.exceptions import KGException
            raise KGException(f"user '{username}' was not created after insert")
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
