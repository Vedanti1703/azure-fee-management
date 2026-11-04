"""
Unit tests for database connection string building, query execution, and retry behavior.
"""

import os
from unittest.mock import patch, MagicMock
import pytest

from shared.db import (
    get_connection_string,
    execute_one,
    execute_query,
    execute_scalar,
    execute_non_query,
    _create_raw_connection,
)


def test_sql_connection_string_from_env():
    """Validates that SQL_CONNECTION_STRING is prioritized from environment."""
    custom_conn = "Driver={ODBC Driver 18 for SQL Server};Server=test-srv;Database=FeeManagement;Uid=sa;Pwd=secret;"
    with patch.dict(os.environ, {"SQL_CONNECTION_STRING": custom_conn}):
        assert get_connection_string() == custom_conn


def test_execute_one_parameterized():
    """Validates execute_one returns single mapped dictionary with parameters."""
    mock_cursor = MagicMock()
    mock_cursor.description = [("StudentID",), ("Name",), ("TotalFee",)]
    mock_cursor.fetchone.return_value = (10, "Riya Mukherjee", 78000.0)

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    with patch("shared.db.get_db_connection") as mock_get_conn:
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        res = execute_one("SELECT StudentID, Name, TotalFee FROM dbo.Students WHERE StudentID = ?", (10,))
        assert res is not None
        assert res["StudentID"] == 10
        assert res["Name"] == "Riya Mukherjee"
        assert res["TotalFee"] == 78000.0
        mock_cursor.execute.assert_called_once_with(
            "SELECT StudentID, Name, TotalFee FROM dbo.Students WHERE StudentID = ?",
            (10,)
        )


def test_tenacity_retry_on_transient_connection_failure():
    """Validates that tenacity retries transient connection errors up to 3 attempts."""
    attempts = 0

    def fail_twice_then_succeed(conn_str):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ConnectionError("Transient network timeout")
        return MagicMock()

    with patch("shared.db.pyodbc.connect", side_effect=fail_twice_then_succeed):
        conn = _create_raw_connection("dummy-conn-str")
        assert conn is not None
        assert attempts == 3
