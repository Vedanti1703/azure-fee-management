"""
Unit tests for status enums and JSON serialization response utilities.
"""

import json
from decimal import Decimal
from datetime import datetime, timezone
import pytest

from shared.status import (
    InvoiceStatus,
    PaymentStatus,
    StudentStatus,
    ReminderType,
    json_response,
    error_response,
)


def test_invoice_status_enums():
    assert InvoiceStatus.PENDING == "PENDING"
    assert InvoiceStatus.PARTIAL == "PARTIAL"
    assert InvoiceStatus.PAID == "PAID"
    assert InvoiceStatus.OVERDUE == "OVERDUE"
    assert InvoiceStatus.CANCELLED == "CANCELLED"


def test_payment_status_enums():
    assert PaymentStatus.SUCCESS == "SUCCESS"
    assert PaymentStatus.PENDING == "PENDING"
    assert PaymentStatus.FAILED == "FAILED"
    assert PaymentStatus.REFUNDED == "REFUNDED"


def test_json_response_with_complex_types():
    data = {
        "amount": Decimal("1250.75"),
        "status": InvoiceStatus.PAID,
        "timestamp": datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc),
        "items": ["Tuition", "Library"]
    }
    resp = json_response(data, status_code=200)

    assert resp.status_code == 200
    assert resp.headers.get("content-type") == "application/json"

    body = json.loads(resp.get_body().decode("utf-8"))
    assert body["amount"] == 1250.75
    assert body["status"] == "PAID"
    assert "2026-09-01" in body["timestamp"]
    assert len(body["items"]) == 2


def test_error_response_structure():
    resp = error_response("Student not found", status_code=404, details={"student_id": 999})

    assert resp.status_code == 404
    body = json.loads(resp.get_body().decode("utf-8"))
    assert body["success"] is False
    assert body["error"]["message"] == "Student not found"
    assert body["error"]["code"] == 404
    assert body["error"]["details"]["student_id"] == 999

