"""
Authentication & Authorization utilities for Azure Functions.
Supports JWT validation via tenant JWKS (production default) and mock mode (local development).
"""

import os
import logging
from typing import Tuple, List, Optional
import jwt
from jwt import PyJWKClient
import azure.functions as func

logger = logging.getLogger(__name__)

# Mock must NEVER be the default. Production default is strictly 'jwt'.
DEFAULT_AUTH_MODE = "jwt"


def get_auth_mode() -> str:
    """Returns the active AUTH_MODE, strictly defaulting to 'jwt'."""
    raw_mode = os.environ.get("AUTH_MODE", DEFAULT_AUTH_MODE)
    mode = raw_mode.strip().lower() if raw_mode else DEFAULT_AUTH_MODE
    return mode if mode else DEFAULT_AUTH_MODE


def log_startup_warning_if_mock():
    """Logs a loud warning banner if mock mode is active."""
    if get_auth_mode() == "mock":
        logger.warning("!" * 75)
        logger.warning("! SECURITY WARNING: AUTH_MODE IS SET TO 'mock' (LOCAL DEV ONLY)           !")
        logger.warning("! Header-based auth (X-Mock-Roles, X-Mock-Oid) is active.                 !")
        logger.warning("! THIS CONFIGURATION MUST NEVER BE USED IN PRODUCTION ENVIRONMENTS.        !")
        logger.warning("!" * 75)


# Trigger startup check on module load
log_startup_warning_if_mock()

# In-memory cache for PyJWKClient instances per tenant
_jwks_clients = {}


def _get_jwks_client(tenant_id: str) -> PyJWKClient:
    """Returns or creates a cached PyJWKClient for the given tenant ID."""
    if tenant_id not in _jwks_clients:
        jwks_url = f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"
        _jwks_clients[tenant_id] = PyJWKClient(jwks_url, cache_jwk_set=True, lifespan=3600)
    return _jwks_clients[tenant_id]


def extract_bearer_token(req: func.HttpRequest) -> Optional[str]:
    """Extracts the Bearer token from the HTTP Authorization header."""
    auth_header = req.headers.get("Authorization") or req.headers.get("authorization")
    if not auth_header:
        return None
    parts = auth_header.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None


def get_caller(req: func.HttpRequest) -> Tuple[Optional[str], List[str]]:
    """
    Identifies the authenticated caller from the request.
    Returns (object_id, roles).

    Modes:
      - 'jwt' (DEFAULT, production): Validates Bearer token using Microsoft Entra ID
        JWKS, verifying issuer, audience, and expiration. Extracts 'oid' (or 'sub')
        and 'roles'.
      - 'mock' (local dev only): Reads roles from 'X-Mock-Roles' and oid from 'X-Mock-Oid'.
        Logs a loud warning when used.
    """
    mode = get_auth_mode()

    if mode == "mock":
        # Loud warning on every invocation in mock mode
        logger.warning("[MOCK AUTH] Processing request using X-Mock-Roles / X-Mock-Oid headers.")
        raw_roles = req.headers.get("X-Mock-Roles") or req.headers.get("x-mock-roles")
        raw_oid = req.headers.get("X-Mock-Oid") or req.headers.get("x-mock-oid")

        if not raw_roles and not raw_oid:
            return (None, [])

        roles = [r.strip() for r in raw_roles.split(",") if r.strip()] if raw_roles else []
        oid = raw_oid.strip() if raw_oid else f"mock-oid-{roles[0].lower() if roles else 'user'}"
        return (oid, roles)

    # Production default: 'jwt' mode
    token = extract_bearer_token(req)
    if not token:
        logger.debug("No Bearer token found in request Authorization header.")
        return (None, [])

    tenant_id = os.environ.get("TENANT_ID")
    api_audience = os.environ.get("API_AUDIENCE")

    if not tenant_id or not api_audience:
        logger.error("TENANT_ID and API_AUDIENCE environment variables must be configured for 'jwt' mode.")
        return (None, [])

    try:
        jwks_client = _get_jwks_client(tenant_id)
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        issuer = f"https://login.microsoftonline.com/{tenant_id}/v2.0"

        decoded = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=api_audience,
            issuer=issuer,
            options={"verify_exp": True}
        )

        oid = decoded.get("oid") or decoded.get("sub")
        raw_roles = decoded.get("roles", [])
        if isinstance(raw_roles, str):
            roles = [raw_roles]
        elif isinstance(raw_roles, list):
            roles = [str(r) for r in raw_roles]
        else:
            roles = []

        return (oid, roles)

    except jwt.ExpiredSignatureError:
        logger.warning("JWT validation failed: Token signature has expired.")
        return (None, [])
    except jwt.InvalidTokenError as ex:
        logger.warning("JWT validation failed: %s", ex)
        return (None, [])
    except Exception as ex:
        logger.error("Unexpected error validating JWT token: %s", ex)
        return (None, [])
