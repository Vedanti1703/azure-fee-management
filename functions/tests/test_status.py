"""
Unit tests for compute_status pure function and status response utilities.
Covers every branch, boundary condition, and data type representation.
"""

from decimal import Decimal
from datetime import date, datetime, timedelta
import pytest

from shared.status import compute_status, json_response, error_response


TODAY = date(2026, 11, 4)
YESTERDAY = TODAY - timedelta(days=1)
TOMORROW = TODAY + timedelta(days=1)
PAST_DATE = TODAY - timedelta(days=30)
FUTURE_DATE = TODAY + timedelta(days=30)


# ==============================================================================
# Branch 1: "Paid" (paid_amount >= total_fee)
# ==============================================================================

def test_paid_exactly_equals_total_future():
    """Boundary: paid exactly equals total fee before due date -> Paid."""
    assert compute_status(
        total_fee=1000.00,
        paid_amount=1000.00,
        due_date=FUTURE_DATE,
        today=TODAY
    ) == "Paid"


def test_paid_exactly_equals_total_due_today():
    """Boundary: paid exactly equals total fee due today -> Paid."""
    assert compute_status(
        total_fee=50000,
        paid_amount=50000,
        due_date=TODAY,
        today=TODAY
    ) == "Paid"


def test_paid_exactly_equals_total_past_due():
    """Boundary: paid exactly equals total fee when due date was yesterday -> Paid."""
    assert compute_status(
        total_fee=Decimal("75000.00"),
        paid_amount=Decimal("75000.00"),
        due_date=YESTERDAY,
        today=TODAY
    ) == "Paid"


def test_paid_greater_than_total():
    """Branch: paid exceeds total fee (overpayment) -> Paid."""
    assert compute_status(
        total_fee=1000.00,
        paid_amount=1200.00,
        due_date=TODAY,
        today=TODAY
    ) == "Paid"


def test_zero_fee_zero_paid():
    """Boundary: total fee is zero and paid is zero -> Paid."""
    assert compute_status(
        total_fee=0,
        paid_amount=0,
        due_date=FUTURE_DATE,
        today=TODAY
    ) == "Paid"


def test_zero_fee_due_in_past():
    """Boundary: total fee is zero and due date is in the past -> Paid."""
    assert compute_status(
        total_fee=0.0,
        paid_amount=0.0,
        due_date=PAST_DATE,
        today=TODAY
    ) == "Paid"


# ==============================================================================
# Branch 2: "Overdue" (due_date < today and paid_amount < total_fee)
# ==============================================================================

def test_overdue_yesterday_zero_paid():
    """Boundary: due yesterday (due_date < today) with zero paid -> Overdue."""
    assert compute_status(
        total_fee=10000,
        paid_amount=0,
        due_date=YESTERDAY,
        today=TODAY
    ) == "Overdue"


def test_overdue_yesterday_partial_paid():
    """Boundary: due yesterday (due_date < today) with partial payment -> Overdue."""
    assert compute_status(
        total_fee=10000,
        paid_amount=4000,
        due_date=YESTERDAY,
        today=TODAY
    ) == "Overdue"


def test_overdue_past_date_zero_paid():
    """Branch: 30 days overdue with zero paid -> Overdue."""
    assert compute_status(
        total_fee=85000.00,
        paid_amount=0.00,
        due_date=PAST_DATE,
        today=TODAY
    ) == "Overdue"


def test_overdue_past_date_partial_paid():
    """Branch: 30 days overdue with partial payment -> Overdue."""
    assert compute_status(
        total_fee=85000.00,
        paid_amount=30000.00,
        due_date=PAST_DATE,
        today=TODAY
    ) == "Overdue"


# ==============================================================================
# Branch 3: "Partially Paid" (0 < paid_amount < total_fee and not overdue)
# ==============================================================================

def test_partially_paid_due_today():
    """Boundary: due today (due_date == today) with partial payment -> Partially Paid."""
    assert compute_status(
        total_fee=1000.00,
        paid_amount=400.00,
        due_date=TODAY,
        today=TODAY
    ) == "Partially Paid"


def test_partially_paid_due_tomorrow():
    """Boundary: due tomorrow (due_date > today) with partial payment -> Partially Paid."""
    assert compute_status(
        total_fee=1000.00,
        paid_amount=999.99,
        due_date=TOMORROW,
        today=TODAY
    ) == "Partially Paid"


def test_partially_paid_future_date():
    """Branch: due in 30 days with partial payment -> Partially Paid."""
    assert compute_status(
        total_fee=120000.00,
        paid_amount=60000.00,
        due_date=FUTURE_DATE,
        today=TODAY
    ) == "Partially Paid"


# ==============================================================================
# Branch 4: "Pending" (otherwise, e.g. paid == 0 and due_date >= today)
# ==============================================================================

def test_pending_due_today_zero_paid():
    """Boundary: due today (due_date == today) with zero paid -> Pending."""
    assert compute_status(
        total_fee=1000.00,
        paid_amount=0.00,
        due_date=TODAY,
        today=TODAY
    ) == "Pending"


def test_pending_due_tomorrow_zero_paid():
    """Boundary: due tomorrow (due_date > today) with zero paid -> Pending."""
    assert compute_status(
        total_fee=1000.00,
        paid_amount=0.00,
        due_date=TOMORROW,
        today=TODAY
    ) == "Pending"


def test_pending_future_date_zero_paid():
    """Branch: due in 30 days with zero paid -> Pending."""
    assert compute_status(
        total_fee=75000.00,
        paid_amount=0.00,
        due_date=FUTURE_DATE,
        today=TODAY
    ) == "Pending"


# ==============================================================================
# Input Types Compatibility (Strings, Datetimes, Decimals)
# ==============================================================================

def test_compute_status_with_iso_strings():
    """Ensures ISO string date inputs are parsed properly."""
    assert compute_status(
        total_fee="5000.00",
        paid_amount="2500.00",
        due_date="2026-11-04",
        today="2026-11-04"
    ) == "Partially Paid"


def test_compute_status_with_datetime_instances():
    """Ensures datetime instances are converted to date."""
    due_dt = datetime(2026, 11, 10, 15, 30, 0)
    today_dt = datetime(2026, 11, 4, 9, 0, 0)
    assert compute_status(
        total_fee=Decimal("1000"),
        paid_amount=Decimal("0"),
        due_date=due_dt,
        today=today_dt
    ) == "Pending"


# ==============================================================================
# Response Utilities Tests
# ==============================================================================

def test_json_response_success():
    resp = json_response({"key": "value"}, status_code=200)
    assert resp.status_code == 200
    assert "application/json" in resp.headers["content-type"]
    assert resp.get_body().decode() == '{"key": "value"}'


def test_error_response_format():
    resp = error_response("Student not found", status_code=404)
    assert resp.status_code == 404
    assert resp.get_body().decode() == '{"error": "Student not found"}'
