from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from jose import jwt

from kg_system.api.deps import require_admin, require_external, require_user
from kg_system.core.config import get_settings
from kg_system.core.exceptions import AuthError

TOKEN = jwt.encode({"sub": "test"}, "test-secret-key-for-testing-only", algorithm="HS256")


def _mock_request():
    req = MagicMock()
    req.app.state.redis = None
    return req


class TestRequireUser:
    def test_missing_header(self):
        with pytest.raises(AuthError, match="missing bearer"):
            require_user(request=_mock_request(), authorization=None)

    def test_empty_token(self):
        with pytest.raises(AuthError, match="empty bearer"):
            require_user(request=_mock_request(), authorization="Bearer ")

    def test_invalid_token(self):
        with pytest.raises(AuthError, match="invalid token"):
            require_user(request=_mock_request(), authorization="Bearer not-a-valid-token")

    def test_success(self):
        payload = require_user(request=_mock_request(), authorization=f"Bearer {TOKEN}")
        assert payload["sub"] == "test"


class TestRequireAdmin:
    def test_token_not_configured(self, monkeypatch):
        monkeypatch.setenv("ADMIN_TOKEN", "")
        get_settings.cache_clear()
        with pytest.raises(AuthError, match="not configured"):
            require_admin(authorization=None)

    def test_missing_header(self):
        with pytest.raises(AuthError, match="missing admin"):
            require_admin(authorization=None)

    def test_wrong_token(self):
        with pytest.raises(AuthError, match="invalid admin"):
            require_admin(authorization="Bearer wrong-token")

    def test_success(self):
        require_admin(authorization="Bearer test-admin-token")


class TestRequireExternal:
    def test_key_not_configured(self, monkeypatch):
        monkeypatch.setenv("EXTERNAL_API_KEY", "")
        get_settings.cache_clear()
        request = MagicMock()
        request.client.host = "127.0.0.1"
        with pytest.raises(AuthError, match="not configured"):
            require_external(request=request, x_api_key="key")

    def test_wrong_key(self):
        request = MagicMock()
        request.client.host = "127.0.0.1"
        with pytest.raises(AuthError, match="invalid external"):
            require_external(request=request, x_api_key="wrong-key")

    def test_ip_not_whitelisted(self):
        request = MagicMock()
        request.client.host = "10.0.0.1"
        with pytest.raises(AuthError, match="not in whitelist"):
            require_external(request=request, x_api_key="test-external-key")

    def test_success(self):
        request = MagicMock()
        request.client.host = "127.0.0.1"
        require_external(request=request, x_api_key="test-external-key")
