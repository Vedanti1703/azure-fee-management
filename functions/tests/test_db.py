"""
Unit tests for database connection string building and query helper execution.
"""

import os
from unittest.mock import patch, MagicMock
import pytest

from shared.db import get_connection_string, execute_query, execute_scalar, execute_non_query


def test_connection_string_from_discrete_variables():
    with patch.dict(os.environ, {
        "AZURE_SQL_CONNECTIONSTRING": "",
        "DB_SERVER": "sql-test.database.windows.net",
        "DB_NAME": "StudentFeeDB",
        "DB_USER": "testadmin",
        "DB_PASSWORD": "SecretPassword123!",
        "DB_DRIVER": "ODBC Driver 18 for SQL Server"
    }, clear=False):
        conn_str = get_connection_string()
        assert "Server=sql-test.database.windows.net" in conn_str
        assert "Database=StudentFeeDB" in conn_str
        assert "Uid=testadmin" in conn_str
        assert "Pwd=SecretPassword123!" in conn_str


def test_connection_string_from_direct_env_override():
    direct_str = "Server=my-custom-host;Database=CustomDB;Uid=u;Pwd=p;"
    with patch.dict(os.environ, {"AZURE_SQL_CONNECTIONSTRING": direct_str}):
        conn_str = get_connection_string()
        assert conn_str == direct_str


def test_execute_query_with_mock_cursor():
    mock_cursor = MagicMock()
    mock_cursor.description = [("student_id",), ("student_code",), ("email",)]
    mock_cursor.fetchall.return_value = [
        (1, "STU-001", "alice@university.edu"),
        (2, "STU-002", "brian@university.edu"),
    ]

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    with patch("shared.db.get_db_connection") as mock_get_conn:
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        results = execute_query("SELECT student_id, student_code, email FROM dbo.Students WHERE status = ?", ("ACTIVE",))
        assert len(results) == 2
        assert results[0]["student_id"] == 1
        assert results[0]["student_code"] == "STU-001"
        assert results[1]["email"] == "brian@university.edu"
        mock_cursor.execute.assert_called_once_with(
            "SELECT student_id, student_code, email FROM dbo.Students WHERE status = ?",
            ("ACTIVE",)
        )

