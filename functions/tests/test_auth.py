"""
Unit tests for get_caller, authentication modes (jwt vs mock), and role extraction.
"""

import os
from unittest.mock import patch, MagicMock
import pytest
import jwt

from shared.auth import (
    get_caller,
    get_auth_mode,
    extract_bearer_token,
    DEFAULT_AUTH_MODE,
)


# ==============================================================================
# Auth Mode Defaults
# ==============================================================================

def test_default_auth_mode_is_jwt():
    """Validates that mock mode is never the default mode."""
    with patch.dict(os.environ, {}, clear=True):
        assert get_auth_mode() == "jwt"
        assert DEFAULT_AUTH_MODE == "jwt"


# ==============================================================================
# Mock Mode Tests
# ==============================================================================

def test_mock_mode_with_roles_and_oid(dummy_request_builder):
    """Mock mode correctly parses X-Mock-Roles and X-Mock-Oid."""
    req = dummy_request_builder(
        headers={
            "X-Mock-Roles": "Admin, Bursar",
            "X-Mock-Oid": "admin-oid-42"
        }
    )
    with patch.dict(os.environ, {"AUTH_MODE": "mock"}):
        oid, roles = get_caller(req)
        assert oid == "admin-oid-42"
        assert roles == ["Admin", "Bursar"]


def test_mock_mode_single_role_default_oid(dummy_request_builder):
    """Mock mode generates a fallback oid if X-Mock-Oid is omitted."""
    req = dummy_request_builder(
        headers={
            "X-Mock-Roles": "Student"
        }
    )
    with patch.dict(os.environ, {"AUTH_MODE": "mock"}):
        oid, roles = get_caller(req)
        assert oid == "mock-oid-student"
        assert roles == ["Student"]


def test_mock_mode_no_headers(dummy_request_builder):
    """Mock mode returns (None, []) when no mock headers are supplied."""
    req = dummy_request_builder(headers={})
    with patch.dict(os.environ, {"AUTH_MODE": "mock"}):
        oid, roles = get_caller(req)
        assert oid is None
        assert roles == []


# ==============================================================================
# JWT Mode Tests
# ==============================================================================

def test_jwt_mode_missing_token(dummy_request_builder):
    """JWT mode returns (None, []) if Authorization header is absent."""
    req = dummy_request_builder(headers={})
    with patch.dict(os.environ, {"AUTH_MODE": "jwt", "TENANT_ID": "t1", "API_AUDIENCE": "aud1"}):
        oid, roles = get_caller(req)
        assert oid is None
        assert roles == []


def test_jwt_mode_valid_token(dummy_request_builder):
    """JWT mode validates token and extracts oid and roles."""
    req = dummy_request_builder(headers={"Authorization": "Bearer mock.jwt.token"})

    mock_jwk_client = MagicMock()
    mock_signing_key = MagicMock()
    mock_signing_key.key = "mock-public-key"
    mock_jwk_client.get_signing_key_from_jwt.return_value = mock_signing_key

    decoded_claims = {
        "oid": "entra-oid-99",
        "roles": ["Admin", "FinanceStaff"],
        "sub": "user-sub-99"
    }

    with patch.dict(os.environ, {"AUTH_MODE": "jwt", "TENANT_ID": "tenant-xyz", "API_AUDIENCE": "api://fees"}):
        with patch("shared.auth._get_jwks_client", return_value=mock_jwk_client):
            with patch("jwt.decode", return_value=decoded_claims):
                oid, roles = get_caller(req)
                assert oid == "entra-oid-99"
                assert "Admin" in roles
                assert "FinanceStaff" in roles


def test_jwt_mode_expired_token(dummy_request_builder):
    """JWT mode returns (None, []) when token is expired."""
    req = dummy_request_builder(headers={"Authorization": "Bearer expired.jwt.token"})

    mock_jwk_client = MagicMock()
    mock_signing_key = MagicMock()
    mock_jwk_client.get_signing_key_from_jwt.return_value = mock_signing_key

    with patch.dict(os.environ, {"AUTH_MODE": "jwt", "TENANT_ID": "tenant-xyz", "API_AUDIENCE": "api://fees"}):
        with patch("shared.auth._get_jwks_client", return_value=mock_jwk_client):
            with patch("jwt.decode", side_effect=jwt.ExpiredSignatureError("Token expired")):
                oid, roles = get_caller(req)
                assert oid is None
                assert roles == []
