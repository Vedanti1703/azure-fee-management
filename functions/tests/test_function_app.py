"""
Unit tests for the Azure Functions HTTP route handlers in function_app.py.
Includes GET /api/students/{studentId}/status and PUT /api/admin/students/{studentId}/fees.
"""

import os
import json
import logging
from unittest.mock import patch, MagicMock
from datetime import date
from decimal import Decimal
import pytest
import azure.functions as func

from function_app import (
    get_student_fee_status,
    update_student_fees,
    get_overdue_students,
    health_check,
)


# ==============================================================================
# GET /api/students/{studentId}/status Tests
# ==============================================================================

def test_student_status_non_integer_id(dummy_request_builder):
    """Returns 400 when studentId is not an integer."""
    req = dummy_request_builder(route_params={"studentId": "abc"})
    resp = get_student_fee_status(req)

    assert resp.status_code == 400
    body = json.loads(resp.get_body().decode())
    assert body["error"] == "Invalid student ID. Must be a positive integer."


def test_student_status_not_found(dummy_request_builder):
    """Returns 404 when student record is not present in database."""
    req = dummy_request_builder(route_params={"studentId": "9999"})

    with patch("function_app.execute_one", return_value=None):
        resp = get_student_fee_status(req)

    assert resp.status_code == 404
    body = json.loads(resp.get_body().decode())
    assert "not found" in body["error"]


def test_student_status_db_error_generic_message(dummy_request_builder):
    """Returns 500 with a generic message on DB error without leaking internal details."""
    req = dummy_request_builder(route_params={"studentId": "101"})

    with patch("function_app.execute_one", side_effect=RuntimeError("ODBC Driver Connection Timeout to 10.0.0.5:1433")):
        resp = get_student_fee_status(req)

    assert resp.status_code == 500
    body = json.loads(resp.get_body().decode())
    assert "internal error" in body["error"]
    assert "10.0.0.5" not in body["error"]
    assert "ODBC" not in body["error"]


def test_student_status_success(dummy_request_builder):
    """Returns 200 with all required fields when student is found."""
    req = dummy_request_builder(route_params={"studentId": "1"})
    mock_student = {
        "StudentID": 1,
        "Name": "Aarav Sharma",
        "TotalFee": Decimal("85000.00"),
        "PaidAmount": Decimal("40000.00"),
        "DueDate": date(2026, 12, 1),
    }

    with patch("function_app.execute_one", return_value=mock_student):
        resp = get_student_fee_status(req)

    assert resp.status_code == 200
    body = json.loads(resp.get_body().decode())

    assert body["studentId"] == 1
    assert body["name"] == "Aarav Sharma"
    assert body["totalFee"] == 85000.0
    assert body["paidAmount"] == 40000.0
    assert body["balance"] == 45000.0
    assert body["dueDate"] == "2026-12-01"
    assert body["status"] in ("Partially Paid", "Overdue", "Paid", "Pending")


# ==============================================================================
# PUT /api/admin/students/{studentId}/fees - Auth & Role Check Tests
# ==============================================================================

def test_admin_update_no_caller_returns_401(dummy_request_builder):
    """Returns 401 Unauthorized when no caller is identified."""
    req = dummy_request_builder(
        method="PUT",
        route_params={"studentId": "1"},
        headers={}, # No mock headers
        body={"totalFee": 50000, "paidAmount": 20000, "dueDate": "2026-12-31"}
    )
    with patch.dict(os.environ, {"AUTH_MODE": "mock"}):
        resp = update_student_fees(req)

    assert resp.status_code == 401
    body = json.loads(resp.get_body().decode())
    assert "Unauthorized" in body["error"]


def test_admin_update_student_role_returns_403(dummy_request_builder):
    """Returns 403 Forbidden when caller does not possess the Admin role."""
    req = dummy_request_builder(
        method="PUT",
        route_params={"studentId": "1"},
        headers={
            "X-Mock-Roles": "Student",
            "X-Mock-Oid": "student-oid-01"
        },
        body={"totalFee": 50000, "paidAmount": 20000, "dueDate": "2026-12-31"}
    )
    with patch.dict(os.environ, {"AUTH_MODE": "mock"}):
        resp = update_student_fees(req)

    assert resp.status_code == 403
    body = json.loads(resp.get_body().decode())
    assert "Forbidden" in body["error"]
    assert "Admin" in body["error"]


def test_admin_update_admin_role_allowed(dummy_request_builder):
    """Allows caller when roles contains Admin."""
    req = dummy_request_builder(
        method="PUT",
        route_params={"studentId": "1"},
        headers={
            "X-Mock-Roles": "Admin",
            "X-Mock-Oid": "admin-oid-99"
        },
        body={"totalFee": 90000, "paidAmount": 90000, "dueDate": "2026-12-31"}
    )
    mock_student = {
        "StudentID": 1,
        "Name": "Aarav Sharma",
        "TotalFee": Decimal("85000.00"),
        "PaidAmount": Decimal("40000.00"),
        "DueDate": date(2026, 11, 1),
    }

    with patch.dict(os.environ, {"AUTH_MODE": "mock"}):
        with patch("function_app.execute_one", return_value=mock_student):
            with patch("function_app.execute_non_query", return_value=1):
                resp = update_student_fees(req)

    assert resp.status_code == 200
    body = json.loads(resp.get_body().decode())
    assert body["studentId"] == 1
    assert body["totalFee"] == 90000.0
    assert body["paidAmount"] == 90000.0
    assert body["status"] == "Paid"


# ==============================================================================
# PUT /api/admin/students/{studentId}/fees - Validation Tests
# ==============================================================================

def test_admin_update_non_integer_id(dummy_request_builder):
    """Returns 400 when route parameter studentId is not an integer."""
    req = dummy_request_builder(
        method="PUT",
        route_params={"studentId": "invalid-id"},
        headers={"X-Mock-Roles": "Admin", "X-Mock-Oid": "admin-1"},
        body={"totalFee": 50000, "paidAmount": 20000, "dueDate": "2026-12-31"}
    )
    with patch.dict(os.environ, {"AUTH_MODE": "mock"}):
        resp = update_student_fees(req)

    assert resp.status_code == 400
    body = json.loads(resp.get_body().decode())
    assert body["error"] == "Validation failed"
    assert "studentId" in body["errors"]


def test_admin_update_validation_negative_numbers(dummy_request_builder):
    """Returns 400 with field-level errors when numbers are negative."""
    req = dummy_request_builder(
        method="PUT",
        route_params={"studentId": "1"},
        headers={"X-Mock-Roles": "Admin", "X-Mock-Oid": "admin-1"},
        body={"totalFee": -500, "paidAmount": -100, "dueDate": "2026-12-31"}
    )
    with patch.dict(os.environ, {"AUTH_MODE": "mock"}):
        resp = update_student_fees(req)

    assert resp.status_code == 400
    body = json.loads(resp.get_body().decode())
    assert body["error"] == "Validation failed"
    assert "non-negative" in body["errors"]["totalFee"]
    assert "non-negative" in body["errors"]["paidAmount"]


def test_admin_update_validation_paid_exceeds_total(dummy_request_builder):
    """Returns 400 with field error when paidAmount exceeds totalFee."""
    req = dummy_request_builder(
        method="PUT",
        route_params={"studentId": "1"},
        headers={"X-Mock-Roles": "Admin", "X-Mock-Oid": "admin-1"},
        body={"totalFee": 50000, "paidAmount": 60000, "dueDate": "2026-12-31"}
    )
    with patch.dict(os.environ, {"AUTH_MODE": "mock"}):
        resp = update_student_fees(req)

    assert resp.status_code == 400
    body = json.loads(resp.get_body().decode())
    assert body["error"] == "Validation failed"
    assert "cannot exceed totalFee" in body["errors"]["paidAmount"]


def test_admin_update_validation_invalid_due_date(dummy_request_builder):
    """Returns 400 with field error when dueDate is not a valid ISO date."""
    req = dummy_request_builder(
        method="PUT",
        route_params={"studentId": "1"},
        headers={"X-Mock-Roles": "Admin", "X-Mock-Oid": "admin-1"},
        body={"totalFee": 50000, "paidAmount": 20000, "dueDate": "31-12-2026"}
    )
    with patch.dict(os.environ, {"AUTH_MODE": "mock"}):
        resp = update_student_fees(req)

    assert resp.status_code == 400
    body = json.loads(resp.get_body().decode())
    assert body["error"] == "Validation failed"
    assert "valid ISO date" in body["errors"]["dueDate"]


def test_admin_update_multiple_field_errors_combined(dummy_request_builder):
    """Returns 400 with all field errors populated simultaneously."""
    req = dummy_request_builder(
        method="PUT",
        route_params={"studentId": "1"},
        headers={"X-Mock-Roles": "Admin", "X-Mock-Oid": "admin-1"},
        body={"totalFee": "bad-number", "paidAmount": -50, "dueDate": "not-a-date"}
    )
    with patch.dict(os.environ, {"AUTH_MODE": "mock"}):
        resp = update_student_fees(req)

    assert resp.status_code == 400
    body = json.loads(resp.get_body().decode())
    assert body["error"] == "Validation failed"
    assert "totalFee" in body["errors"]
    assert "paidAmount" in body["errors"]
    assert "dueDate" in body["errors"]


# ==============================================================================
# PUT /api/admin/students/{studentId}/fees - DB, 404 & Audit Logging Tests
# ==============================================================================

def test_admin_update_student_not_found(dummy_request_builder):
    """Returns 404 when student row does not exist in database."""
    req = dummy_request_builder(
        method="PUT",
        route_params={"studentId": "888"},
        headers={"X-Mock-Roles": "Admin", "X-Mock-Oid": "admin-1"},
        body={"totalFee": 50000, "paidAmount": 20000, "dueDate": "2026-12-31"}
    )
    with patch.dict(os.environ, {"AUTH_MODE": "mock"}):
        with patch("function_app.execute_one", return_value=None):
            resp = update_student_fees(req)

    assert resp.status_code == 404
    body = json.loads(resp.get_body().decode())
    assert "not found" in body["error"]


def test_admin_update_writes_audit_log_without_pii(dummy_request_builder, caplog):
    """Verifies that an audit log line is written with admin_oid, studentId, and no PII."""
    req = dummy_request_builder(
        method="PUT",
        route_params={"studentId": "42"},
        headers={"X-Mock-Roles": "Admin", "X-Mock-Oid": "admin-oid-777"},
        body={"totalFee": 95000.0, "paidAmount": 50000.0, "dueDate": "2026-12-15"}
    )
    mock_old_student = {
        "StudentID": 42,
        "Name": "Secret Student Name",
        "TotalFee": Decimal("80000.00"),
        "PaidAmount": Decimal("20000.00"),
        "DueDate": date(2026, 10, 15),
    }

    with patch.dict(os.environ, {"AUTH_MODE": "mock"}):
        with patch("function_app.execute_one", return_value=mock_old_student):
            with patch("function_app.execute_non_query", return_value=1):
                with caplog.at_level(logging.INFO, logger="FeeManagement.Audit"):
                    resp = update_student_fees(req)

    assert resp.status_code == 200

    # Inspect audit log records
    audit_messages = [rec.message for rec in caplog.records if rec.name == "FeeManagement.Audit"]
    assert len(audit_messages) == 1
    log_line = audit_messages[0]

    # Verify admin_oid and studentId are present
    assert "admin-oid-777" in log_line
    assert ("studentId=42" in log_line or "student_id=42" in log_line)
    assert "old_values" in log_line
    assert "new_values" in log_line

    # Verify NO PII beyond IDs (student's name must NOT be in audit log)
    assert "Secret Student Name" not in log_line


# ==============================================================================
# GET /api/overdue Tests
# ==============================================================================

def test_get_overdue_default_params(dummy_request_builder):
    """GET /api/overdue defaults to top=100 and skip=0, returning expected JSON schema."""
    req = dummy_request_builder(params={})

    mock_db_rows = [
        {
            "StudentID": 13,
            "Name": "Siddharth Malhotra",
            "Email": "siddharth@example.com",
            "Course": "B.Tech Computer Science",
            "TotalFee": Decimal("85000.00"),
            "PaidAmount": Decimal("0.00"),
            "DueDate": date(2026, 10, 30),
            "BalanceAmount": Decimal("85000.00"),
        },
        {
            "StudentID": 14,
            "Name": "Pooja Choudhary",
            "Email": "pooja@example.com",
            "Course": "MCA",
            "TotalFee": Decimal("70000.00"),
            "PaidAmount": Decimal("20000.00"),
            "DueDate": date(2026, 10, 20),
            "BalanceAmount": Decimal("50000.00"),
        }
    ]

    with patch("function_app.execute_query", return_value=mock_db_rows) as mock_exec:
        resp = get_overdue_students(req)

    assert resp.status_code == 200
    mock_exec.assert_called_once_with("EXEC dbo.sp_GetOverdueStudents @Top = ?, @Skip = ?", (100, 0))

    body = json.loads(resp.get_body().decode())
    assert body["count"] == 2
    assert len(body["students"]) == 2

    first = body["students"][0]
    assert first["studentId"] == 13
    assert first["name"] == "Siddharth Malhotra"
    assert first["email"] == "siddharth@example.com"
    assert first["balance"] == 85000.0
    assert first["dueDate"] == "2026-10-30"
    assert first["daysOverdue"] >= 0


def test_get_overdue_custom_pagination(dummy_request_builder):
    """GET /api/overdue passes custom top and skip parameters to the stored procedure."""
    req = dummy_request_builder(params={"top": "50", "skip": "25"})

    with patch("function_app.execute_query", return_value=[]) as mock_exec:
        resp = get_overdue_students(req)

    assert resp.status_code == 200
    mock_exec.assert_called_once_with("EXEC dbo.sp_GetOverdueStudents @Top = ?, @Skip = ?", (50, 25))

    body = json.loads(resp.get_body().decode())
    assert body["count"] == 0
    assert body["students"] == []


def test_get_overdue_top_clamped_to_max_500(dummy_request_builder):
    """GET /api/overdue clamps top to maximum 500."""
    req = dummy_request_builder(params={"top": "999", "skip": "0"})

    with patch("function_app.execute_query", return_value=[]) as mock_exec:
        resp = get_overdue_students(req)

    assert resp.status_code == 200
    mock_exec.assert_called_once_with("EXEC dbo.sp_GetOverdueStudents @Top = ?, @Skip = ?", (500, 0))


def test_get_overdue_invalid_parameters_return_400(dummy_request_builder):
    """GET /api/overdue returns 400 when top or skip are invalid integers."""
    # Invalid top
    req1 = dummy_request_builder(params={"top": "not-an-int"})
    resp1 = get_overdue_students(req1)
    assert resp1.status_code == 400

    # Negative top
    req2 = dummy_request_builder(params={"top": "-10"})
    resp2 = get_overdue_students(req2)
    assert resp2.status_code == 400

    # Invalid skip
    req3 = dummy_request_builder(params={"skip": "abc"})
    resp3 = get_overdue_students(req3)
    assert resp3.status_code == 400

    # Negative skip
    req4 = dummy_request_builder(params={"skip": "-1"})
    resp4 = get_overdue_students(req4)
    assert resp4.status_code == 400


def test_get_overdue_database_error_generic_500(dummy_request_builder):
    """GET /api/overdue logs error and returns generic 500 on database failure."""
    req = dummy_request_builder(params={})

    with patch("function_app.execute_query", side_effect=Exception("Database connection terminated")):
        resp = get_overdue_students(req)

    assert resp.status_code == 500
    body = json.loads(resp.get_body().decode())
    assert "internal error" in body["error"]


# ==============================================================================
# Health Check & Observability Tests
# ==============================================================================

def test_health_check_healthy(dummy_request_builder):
    """GET /api/health executes SELECT 1 and returns 200 with healthy status."""
    req = dummy_request_builder(headers={"x-ms-client-tracking-id": "test-track-123"})

    with patch("function_app.execute_scalar", return_value=1) as mock_exec:
        resp = health_check(req)

    assert resp.status_code == 200
    mock_exec.assert_called_once_with("SELECT 1")
    body = json.loads(resp.get_body().decode())
    assert body["status"] == "healthy"
    assert body["database"] == "connected"
    assert resp.headers.get("x-ms-client-tracking-id") == "test-track-123"


def test_health_check_unhealthy(dummy_request_builder):
    """GET /api/health returns 503 when SELECT 1 raises an exception."""
    req = dummy_request_builder()

    with patch("function_app.execute_scalar", side_effect=Exception("Database unreachable")):
        resp = health_check(req)

    assert resp.status_code == 503
    body = json.loads(resp.get_body().decode())
    assert body["status"] == "unhealthy"
    assert "Database connectivity check failed" in body["error"]
    assert "x-ms-client-tracking-id" in resp.headers


def test_observability_structured_log_line(dummy_request_builder, caplog):
    """Verifies request_id, operation, studentId, and duration_ms in logs, with zero PII."""
    req = dummy_request_builder(
        route_params={"studentId": "7"},
        headers={"x-ms-client-tracking-id": "client-uuid-9999"}
    )
    mock_student = {
        "StudentID": 7,
        "Name": "Ishan Kulkarni",
        "TotalFee": Decimal("120000.00"),
        "PaidAmount": Decimal("60000.00"),
        "DueDate": date(2026, 12, 1),
    }

    with patch("function_app.execute_one", return_value=mock_student):
        with caplog.at_level(logging.INFO, logger="FeeManagement.App"):
            resp = get_student_fee_status(req)

    assert resp.status_code == 200
    assert resp.headers.get("x-ms-client-tracking-id") == "client-uuid-9999"

    # Find the structured log message
    app_messages = [rec.message for rec in caplog.records if rec.name == "FeeManagement.App"]
    assert any("request_id=client-uuid-9999" in m for m in app_messages)
    assert any("operation=get_student_fee_status" in m for m in app_messages)
    assert any("studentId=7" in m for m in app_messages)
    assert any("duration_ms=" in m for m in app_messages)

    # Privacy check: emails, tokens, and connection strings must NEVER be in logs
    all_logs = " ".join(rec.message for rec in caplog.records)
    assert "ishan@example.com" not in all_logs
    assert "Bearer" not in all_logs
    assert "Password" not in all_logs
    assert "Driver=" not in all_logs


