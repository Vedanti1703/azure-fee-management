"""
Unit tests for JWT authentication and role validation.
"""

import pytest
import jwt
from datetime import datetime, timedelta, timezone

from shared.auth import (
    generate_token,
    authenticate_request,
    require_role,
    JWT_SECRET_KEY,
    JWT_ALGORITHM,
    JWT_ISSUER,
    JWT_AUDIENCE,
)


def test_generate_and_authenticate_valid_token(dummy_request_builder):
    token = generate_token(subject="user_123", roles=["ADMIN", "BURSAR"], email="admin@university.edu")
    req = dummy_request_builder(headers={"Authorization": f"Bearer {token}"})

    claims = authenticate_request(req)
    assert claims["sub"] == "user_123"
    assert "ADMIN" in claims["roles"]
    assert claims["email"] == "admin@university.edu"


def test_missing_authorization_header(dummy_request_builder):
    req = dummy_request_builder(headers={})
    with pytest.raises(ValueError, match="Missing or malformed Authorization header"):
        authenticate_request(req)


def test_expired_token(dummy_request_builder):
    now = datetime.now(timezone.utc)
    expired_payload = {
        "sub": "user_expired",
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "iat": now - timedelta(hours=2),
        "exp": now - timedelta(hours=1),
        "roles": ["STUDENT"]
    }
    expired_token = jwt.encode(expired_payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    req = dummy_request_builder(headers={"Authorization": f"Bearer {expired_token}"})

    with pytest.raises(ValueError, match="Token has expired"):
        authenticate_request(req)


def test_invalid_audience_token(dummy_request_builder):
    now = datetime.now(timezone.utc)
    bad_aud_payload = {
        "sub": "user_test",
        "iss": JWT_ISSUER,
        "aud": "wrong-audience",
        "iat": now,
        "exp": now + timedelta(hours=1),
        "roles": ["STUDENT"]
    }
    bad_token = jwt.encode(bad_aud_payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    req = dummy_request_builder(headers={"Authorization": f"Bearer {bad_token}"})

    with pytest.raises(ValueError, match="Invalid token audience"):
        authenticate_request(req)


def test_require_role_matching():
    claims = {"sub": "staff_01", "roles": ["BURSAR"]}
    assert require_role(claims, ["ADMIN", "BURSAR"]) is True
    assert require_role(claims, ["STUDENT"]) is False

