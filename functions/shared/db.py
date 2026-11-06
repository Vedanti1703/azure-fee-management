
"""
Database connection and parameterized query utilities for SQL Server / Azure SQL.
Uses Microsoft's mssql-python driver with short exponential backoff retries.
"""

import os
import re
import logging
from typing import List, Dict, Any, Optional, Tuple, Union
from contextlib import contextmanager

import mssql_python

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception,
    before_sleep_log,
)

logger = logging.getLogger(__name__)


def _sanitize_log_message(msg: Any) -> str:
    """Removes passwords and sensitive connection parameters from logs."""
    return re.sub(
        r'(?i)(pwd|password|secret|key)=[^;,\s]+',
        r'\1=***',
        str(msg)
    )


def get_connection_string() -> str:
    """
    Retrieves the SQL connection string from environment variables.
    Removes legacy pyodbc-only connection string keywords.
    """
    conn_str = (
        os.environ.get("SQL_CONNECTION_STRING")
        or os.environ.get("AZURE_SQL_CONNECTIONSTRING")
    )

    if conn_str:
        # mssql-python manages its own driver.
        conn_str = re.sub(
            r'(?i)(?:^|;)\s*Driver\s*=\s*(?:\{[^}]*\}|[^;]*)\s*;?',
            ';',
            conn_str
        )

        # Connection timeout is passed to connect(), not in the string.
        conn_str = re.sub(
            r'(?i)(?:^|;)\s*Connection Timeout\s*=\s*[^;]*;?',
            ';',
            conn_str
        )

        return conn_str.strip(";")

    server = os.environ.get("DB_SERVER", "localhost,1433")
    database = os.environ.get("DB_NAME", "FeeManagement")
    user = os.environ.get("DB_USER", "sa")
    password = (
        os.environ.get("MSSQL_SA_PASSWORD")
        or os.environ.get("DB_PASSWORD", "")
    )
    trust_cert = os.environ.get(
        "DB_TRUST_SERVER_CERTIFICATE", "yes"
    )
    encrypt = os.environ.get("DB_ENCRYPT", "yes")

    return (
        f"Server={server};"
        f"Database={database};"
        f"UID={user};"
        f"PWD={{{password}}};"
        f"Encrypt={encrypt};"
        f"TrustServerCertificate={trust_cert};"
    )


def _is_transient_db_error(exc: BaseException) -> bool:
    """Identifies database/network errors eligible for retry."""
    if isinstance(
        exc,
        (
            mssql_python.OperationalError,
            mssql_python.DatabaseError,
        )
    ):
        return True

    return isinstance(
        exc,
        (ConnectionError, TimeoutError, OSError)
    )


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(
        multiplier=0.5,
        min=0.5,
        max=2.0
    ),
    retry=retry_if_exception(_is_transient_db_error),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _create_raw_connection(conn_str: str):
    """Creates a database connection with exponential backoff."""
    return mssql_python.connect(conn_str, timeout=15)


@contextmanager
def get_db_connection():
    """
    Provides a managed database connection with automatic commit/rollback.
    """
    conn_str = get_connection_string()
    conn = None

    try:
        conn = _create_raw_connection(conn_str)
        yield conn
        conn.commit()

    except Exception as ex:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass

        logger.error(
            "Database connection or execution failed: %s",
            _sanitize_log_message(ex)
        )
        raise

    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def execute_one(
    sql: str,
    params: Optional[Union[Tuple, List]] = None
) -> Optional[Dict[str, Any]]:
    """Executes a parameterized query and returns its first row."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        try:
            cursor.execute(sql, tuple(params or ()))
            columns = [
                column[0] for column in cursor.description
            ] if cursor.description else []

            row = cursor.fetchone()

            if not row:
                return None

            return dict(zip(columns, row))

        finally:
            cursor.close()


def execute_query(
    sql: str,
    params: Optional[Union[Tuple, List]] = None
) -> List[Dict[str, Any]]:
    """Executes a SELECT query and returns rows as dictionaries."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        try:
            cursor.execute(sql, tuple(params or ()))

            columns = [
                column[0] for column in cursor.description
            ] if cursor.description else []

            rows = cursor.fetchall()

            return [
                dict(zip(columns, row))
                for row in rows
            ]

        finally:
            cursor.close()


def execute_scalar(
    sql: str,
    params: Optional[Union[Tuple, List]] = None
) -> Any:
    """Executes a query returning a single scalar value."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        try:
            cursor.execute(sql, tuple(params or ()))
            row = cursor.fetchone()

            return row[0] if row else None

        finally:
            cursor.close()


def execute_non_query(
    sql: str,
    params: Optional[Union[Tuple, List]] = None
) -> int:
    """Executes INSERT, UPDATE, or DELETE and returns rows affected."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        try:
            cursor.execute(sql, tuple(params or ()))
            return cursor.rowcount

        finally:
            cursor.close()
