
"""
Unit tests for database connection string building, query execution, and retry behavior.
"""

import os
from unittest.mock import patch, MagicMock

from shared.db import (
    get_connection_string,
    execute_one,
    execute_query,
    execute_scalar,
    execute_non_query,
    _create_raw_connection,
)


def test_sql_connection_string_from_env():
    """Validates SQL_CONNECTION_STRING priority and legacy driver removal."""

    custom_conn = (
        "Driver={ODBC Driver 18 for SQL Server};"
        "Server=test-srv;"
        "Database=FeeManagement;"
        "Uid=sa;"
        "Pwd=secret;"
    )

    expected_conn = (
        "Server=test-srv;"
        "Database=FeeManagement;"
        "Uid=sa;"
        "Pwd=secret"
    )

    with patch.dict(
        os.environ,
        {"SQL_CONNECTION_STRING": custom_conn}
    ):
        assert get_connection_string() == expected_conn


def test_execute_one_parameterized():
    """Validates execute_one returns a mapped dictionary with parameters."""

    mock_cursor = MagicMock()
    mock_cursor.description = [
        ("StudentID",),
        ("Name",),
        ("TotalFee",)
    ]

    mock_cursor.fetchone.return_value = (
        10,
        "Riya Mukherjee",
        78000.0
    )

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    with patch("shared.db.get_db_connection") as mock_get_conn:
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        res = execute_one(
            "SELECT StudentID, Name, TotalFee "
            "FROM dbo.Students WHERE StudentID = ?",
            (10,)
        )

        assert res is not None
        assert res["StudentID"] == 10
        assert res["Name"] == "Riya Mukherjee"
        assert res["TotalFee"] == 78000.0

        mock_cursor.execute.assert_called_once_with(
            "SELECT StudentID, Name, TotalFee "
            "FROM dbo.Students WHERE StudentID = ?",
            (10,)
        )


def test_tenacity_retry_on_transient_connection_failure():
    """Validates retries up to 3 attempts using mssql-python."""

    attempts = 0

    def fail_twice_then_succeed(conn_str, **kwargs):
        nonlocal attempts
        attempts += 1

        if attempts < 3:
            raise ConnectionError("Transient network timeout")

        return MagicMock()

    with patch(
        "shared.db.mssql_python.connect",
        side_effect=fail_twice_then_succeed
    ):
        conn = _create_raw_connection("dummy-conn-str")

        assert conn is not None
        assert attempts == 3


def test_execute_query():
    """Validates execute_query returns multiple rows as dictionaries."""

    mock_cursor = MagicMock()
    mock_cursor.description = [
        ("StudentID",),
        ("Name",)
    ]

    mock_cursor.fetchall.return_value = [
        (1, "Aarav"),
        (2, "Riya")
    ]

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    with patch("shared.db.get_db_connection") as mock_get_conn:
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        result = execute_query(
            "SELECT StudentID, Name FROM dbo.Students",
            ()
        )

        assert len(result) == 2
        assert result[0] == {"StudentID": 1, "Name": "Aarav"}
        assert result[1] == {"StudentID": 2, "Name": "Riya"}


def test_execute_scalar():
    """Validates execute_scalar returns a single value."""

    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = (150,)

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    with patch("shared.db.get_db_connection") as mock_get_conn:
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        result = execute_scalar(
            "SELECT COUNT(*) FROM dbo.Students"
        )

        assert result == 150


def test_execute_non_query():
    """Validates execute_non_query returns affected row count."""

    mock_cursor = MagicMock()
    mock_cursor.rowcount = 1

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    with patch("shared.db.get_db_connection") as mock_get_conn:
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        result = execute_non_query(
            "UPDATE dbo.Students SET PaidAmount = ? WHERE StudentID = ?",
            (5000, 10)
        )

        assert result == 1

        mock_cursor.execute.assert_called_once_with(
            "UPDATE dbo.Students SET PaidAmount = ? WHERE StudentID = ?",
            (5000, 10)
        )
