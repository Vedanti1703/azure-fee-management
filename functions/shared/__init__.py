"""
Shared utilities package for Azure Student Fee Management System.
"""

from .status import (
    InvoiceStatus,
    PaymentStatus,
    StudentStatus,
    ReminderType,
    json_response,
    error_response,
)
from .auth import authenticate_request, generate_token, require_role
from .db import get_db_connection, execute_query, execute_non_query, execute_scalar

__all__ = [
    "InvoiceStatus",
    "PaymentStatus",
    "StudentStatus",
    "ReminderType",
    "json_response",
    "error_response",
    "authenticate_request",
    "generate_token",
    "require_role",
    "get_db_connection",
    "execute_query",
    "execute_non_query",
    "execute_scalar",
]

