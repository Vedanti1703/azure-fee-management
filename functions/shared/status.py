"""
Status Enums and HTTP Response Builders for Fee Management System.
"""

from enum import Enum
import json
from decimal import Decimal
from datetime import date, datetime
from typing import Any, Dict, Optional
import azure.functions as func


class InvoiceStatus(str, Enum):
    PENDING = "PENDING"
    PARTIAL = "PARTIAL"
    PAID = "PAID"
    OVERDUE = "OVERDUE"
    CANCELLED = "CANCELLED"


class PaymentStatus(str, Enum):
    SUCCESS = "SUCCESS"
    PENDING = "PENDING"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class StudentStatus(str, Enum):
    ACTIVE = "ACTIVE"
    GRADUATED = "GRADUATED"
    SUSPENDED = "SUSPENDED"
    WITHDRAWN = "WITHDRAWN"


class ReminderType(str, Enum):
    UPCOMING_DUE = "UPCOMING_DUE"
    DUE_TODAY = "DUE_TODAY"
    OVERDUE_FIRST = "OVERDUE_FIRST"
    OVERDUE_FINAL = "OVERDUE_FINAL"
    CUSTOM = "CUSTOM"


class CustomJSONEncoder(json.JSONEncoder):
    """Encodes custom Python objects like Decimal, datetime, and Enums to JSON."""
    def default(self, obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, Enum):
            return obj.value
        return super().default(obj)


def json_response(
    data: Any,
    status_code: int = 200,
    headers: Optional[Dict[str, str]] = None
) -> func.HttpResponse:
    """Builds a standardized application/json HttpResponse."""
    default_headers = {"Content-Type": "application/json"}
    if headers:
        default_headers.update(headers)

    body = json.dumps(data, cls=CustomJSONEncoder)
    return func.HttpResponse(body=body, status_code=status_code, headers=default_headers)


def error_response(
    message: str,
    status_code: int = 400,
    details: Optional[Any] = None
) -> func.HttpResponse:
    """Builds a standardized error HttpResponse."""
    payload = {
        "success": False,
        "error": {
            "message": message,
            "code": status_code,
            "details": details or {}
        }
    }
    return json_response(payload, status_code=status_code)

