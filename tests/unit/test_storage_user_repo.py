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
        fake_pg.fetchrow.return_value = {
            "username": "bob", "password_hash": "xyz", "role": "user", "created_at": "", "updated_at": "",
        }
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
