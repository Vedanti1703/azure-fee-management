
"""
Pytest configuration and shared fixtures for Azure Functions tests.
"""

import os
import sys
import pytest

# Add functions root directory to sys.path
sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
)

# Set environment variables for testing
os.environ["ENVIRONMENT"] = "testing"
os.environ["AUTH_MODE"] = "mock"

os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-unit-testing-32-chars"
os.environ["JWT_ALGORITHM"] = "HS256"
os.environ["JWT_ISSUER"] = "fee-management-service"
os.environ["JWT_AUDIENCE"] = "fee-management-client"

os.environ["DB_SERVER"] = "localhost,1433"
os.environ["DB_NAME"] = "StudentFeeManagementDB_Test"
os.environ["DB_USER"] = "sa"
os.environ["DB_PASSWORD"] = "TestPassword123!"


@pytest.fixture
def dummy_request_builder():
    """Helper fixture to create mock Azure Functions HttpRequest objects."""

    import azure.functions as func

    def _create_req(
        method="GET",
        url="http://localhost:7071/api/test",
        headers=None,
        params=None,
        route_params=None,
        body=None
    ):
        body_bytes = None

        if body is not None:
            if isinstance(body, str):
                body_bytes = body.encode("utf-8")
            else:
                import json
                body_bytes = json.dumps(body).encode("utf-8")

        # No headers argument: use default Admin identity
        if headers is None:
            request_headers = {
                "X-Mock-Roles": "Admin",
                "X-Mock-Oid": "test-admin-oid"
            }

        # Explicitly empty headers: no identity
        elif not headers:
            request_headers = {}

        # Explicit mock headers: preserve exactly what the test supplied
        elif any(
            key.lower() in ("x-mock-roles", "x-mock-oid")
            for key in headers
        ):
            request_headers = headers.copy()

        # Other custom headers: add default Admin identity
        else:
            request_headers = {
                "X-Mock-Roles": "Admin",
                "X-Mock-Oid": "test-admin-oid",
                **headers
            }

        return func.HttpRequest(
            method=method,
            url=url,
            headers=request_headers,
            params=params or {},
            route_params=route_params or {},
            body=body_bytes
        )

    return _create_req
