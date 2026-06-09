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
