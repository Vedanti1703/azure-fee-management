"""
Authentication & Authorization utilities for Azure Functions.
Supports JWT Bearer token validation and role checks via environment variables.
"""

import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
import jwt
import azure.functions as func

logger = logging.getLogger(__name__)

JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-insecure-secret-placeholder-change-in-prod")
JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
JWT_ISSUER = os.environ.get("JWT_ISSUER", "fee-management-service")
JWT_AUDIENCE = os.environ.get("JWT_AUDIENCE", "fee-management-client")
AUTH_MODE = os.environ.get("AUTH_MODE", "JWT").upper()


def generate_token(
    subject: str,
    roles: Optional[List[str]] = None,
    email: Optional[str] = None,
    expires_minutes: int = 60
) -> str:
    """
    Generate a signed JWT token (useful for local development, tests, and CLI callers).
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
        "roles": roles or ["STUDENT"],
        "email": email or f"{subject}@university.edu",
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def extract_bearer_token(req: func.HttpRequest) -> Optional[str]:
    """Extract Bearer token from the HTTP Authorization header."""
    auth_header = req.headers.get("Authorization") or req.headers.get("authorization")
    if not auth_header:
        return None
    parts = auth_header.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None


def authenticate_request(req: func.HttpRequest) -> Dict[str, Any]:
    """
    Validates the bearer token in the incoming request.
    Raises ValueError with explanation if invalid or missing.
    Returns the decoded token claims dictionary.
    """
    # Allow mock bypass only in explicit local dev testing if AUTH_MODE is NONE
    if AUTH_MODE == "NONE":
        logger.warning("AUTH_MODE is NONE. Authentication bypassed for local testing.")
        return {"sub": "dev-user", "roles": ["ADMIN", "BURSAR"], "email": "dev@university.edu"}

    token = extract_bearer_token(req)
    if not token:
        raise ValueError("Missing or malformed Authorization header. Expected 'Bearer <token>'.")

    try:
        decoded = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
            issuer=JWT_ISSUER,
            audience=JWT_AUDIENCE,
        )
        return decoded
    except jwt.ExpiredSignatureError:
        raise ValueError("Token has expired.")
    except jwt.InvalidAudienceError:
        raise ValueError("Invalid token audience.")
    except jwt.InvalidIssuerError:
        raise ValueError("Invalid token issuer.")
    except jwt.InvalidTokenError as ex:
        raise ValueError(f"Invalid token: {str(ex)}")


def require_role(claims: Dict[str, Any], allowed_roles: List[str]) -> bool:
    """
    Checks if any role assigned to the user matches the allowed roles.
    """
    user_roles = claims.get("roles", [])
    if isinstance(user_roles, str):
        user_roles = [user_roles]
    return any(role in allowed_roles for role in user_roles)

