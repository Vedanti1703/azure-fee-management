"""
Unit tests for scripts/send_reminders_local.py.
Tests paging, email formatting, and 3-attempt exponential backoff retry logic.
"""

import os
import sys
from unittest.mock import patch, MagicMock
import pytest

# Ensure scripts directory is in sys.path
scripts_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
if scripts_dir not in sys.path:
    sys.path.insert(0, scripts_dir)

from send_reminders_local import (
    fetch_all_overdue_students,
    build_email_message,
    send_email_with_retry,
)


def test_build_email_message():
    student = {
        "studentId": 10,
        "name": "Riya Mukherjee",
        "email": "riya@example.com",
        "balance": 53000.0,
        "dueDate": "2026-10-20",
        "daysOverdue": 15
    }

    msg = build_email_message(student, "billing@university.edu", "Financial Services")

    assert msg["To"] == "riya@example.com"
    assert "Financial Services" in msg["From"]
    assert "billing@university.edu" in msg["From"]
    assert "Riya Mukherjee" in msg["Subject"]

    # Check payload contains plain text and HTML
    parts = msg.get_payload()
    assert len(parts) == 2

    text_body = parts[0].get_payload(decode=True).decode("utf-8")
    assert "Riya Mukherjee" in text_body
    assert "$53,000.00" in text_body
    assert "2026-10-20" in text_body
    assert "15 day(s)" in text_body or "15" in text_body

    html_body = parts[1].get_payload(decode=True).decode("utf-8")
    assert "$53,000.00" in html_body
    assert "Riya Mukherjee" in html_body


def test_fetch_all_overdue_students_pagination():
    """Validates that fetch_all_overdue_students loops across multiple pages."""
    page_1 = {
        "count": 2,
        "students": [
            {"studentId": 1, "name": "A", "email": "a@ex.com", "balance": 100, "dueDate": "2026-10-01", "daysOverdue": 30},
            {"studentId": 2, "name": "B", "email": "b@ex.com", "balance": 200, "dueDate": "2026-10-02", "daysOverdue": 29},
        ]
    }
    page_2 = {
        "count": 1,
        "students": [
            {"studentId": 3, "name": "C", "email": "c@ex.com", "balance": 300, "dueDate": "2026-10-03", "daysOverdue": 28},
        ]
    }

    mock_responses = [
        MagicMock(status_code=200, json=lambda: page_1),
        MagicMock(status_code=200, json=lambda: page_2),
    ]

    with patch("requests.get", side_effect=mock_responses) as mock_get:
        students = fetch_all_overdue_students("http://localhost:7071", page_size=2)

    assert len(students) == 3
    assert [s["studentId"] for s in students] == [1, 2, 3]
    assert mock_get.call_count == 2


def test_send_email_dry_run():
    student = {
        "name": "Dry Run User",
        "email": "dry@example.com",
        "balance": 1200.0,
        "dueDate": "2026-10-01",
        "daysOverdue": 30
    }
    # In dry-run mode, should not attempt SMTP connection and return True
    success = send_email_with_retry(student, "localhost", 1025, "billing@edu", "Office", dry_run=True)
    assert success is True


def test_send_email_retry_success():
    """Fails once on SMTP error, then succeeds on retry."""
    student = {
        "name": "Retry User",
        "email": "retry@example.com",
        "balance": 2500.0,
        "dueDate": "2026-10-05",
        "daysOverdue": 25
    }

    mock_smtp_instance = MagicMock()
    mock_smtp_factory = MagicMock()

    call_count = 0
    def smtp_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ConnectionRefusedError("SMTP server down temporarily")
        return mock_smtp_instance

    mock_smtp_factory.side_effect = smtp_side_effect
    mock_smtp_instance.__enter__.return_value = mock_smtp_instance

    with patch("smtplib.SMTP", mock_smtp_factory), patch("time.sleep"):
        success = send_email_with_retry(student, "localhost", 1025, "billing@edu", "Office", dry_run=False)

    assert success is True
    assert call_count == 2


def test_send_email_exceeds_retries_returns_false_and_does_not_raise():
    """Fails all 3 attempts, logs error, returns False, and does not raise an exception."""
    student = {
        "name": "Failing User",
        "email": "fail@example.com",
        "balance": 5000.0,
        "dueDate": "2026-09-01",
        "daysOverdue": 60
    }

    mock_smtp_factory = MagicMock(side_effect=ConnectionRefusedError("Connection refused"))

    with patch("smtplib.SMTP", mock_smtp_factory), patch("time.sleep"):
        success = send_email_with_retry(student, "localhost", 1025, "billing@edu", "Office", dry_run=False)

    assert success is False
    assert mock_smtp_factory.call_count == 3

