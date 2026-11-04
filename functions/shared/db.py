"""
Database connection and parameterized query utilities for SQL Server / Azure SQL.
Reads SQL_CONNECTION_STRING from environment with short exponential backoff retries via tenacity.
"""

import os
import re
import logging
from typing import List, Dict, Any, Optional, Tuple, Union
from contextlib import contextmanager

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception,
    before_sleep_log,
)

logger = logging.getLogger(__name__)


def _sanitize_log_message(msg: Any) -> str:
    """Removes passwords and sensitive connection parameters from log messages."""
    return re.sub(r'(?i)(pwd|password|secret|key)=[^;,\s]+', r'\1=***', str(msg))

# pyodbc import with graceful fallback
try:
    import pyodbc
except ImportError:
    pyodbc = None


def get_connection_string() -> str:
    """
    Retrieves the database connection string from environment variables.
    Checks SQL_CONNECTION_STRING first, then AZURE_SQL_CONNECTIONSTRING,
    and falls back to discrete environment variables.
    """
    conn_str = os.environ.get("SQL_CONNECTION_STRING") or os.environ.get("AZURE_SQL_CONNECTIONSTRING")
    if conn_str:
        return conn_str

    server = os.environ.get("DB_SERVER", "localhost,1433")
    database = os.environ.get("DB_NAME", "FeeManagement")
    user = os.environ.get("DB_USER", "sa")
    password = os.environ.get("MSSQL_SA_PASSWORD") or os.environ.get("DB_PASSWORD", "")
    driver = os.environ.get("DB_DRIVER", "ODBC Driver 18 for SQL Server")
    trust_cert = os.environ.get("DB_TRUST_SERVER_CERTIFICATE", "yes")
    encrypt = os.environ.get("DB_ENCRYPT", "yes")

    return (
        f"Driver={{{driver}}};"
        f"Server={server};"
        f"Database={database};"
        f"Uid={user};"
        f"Pwd={password};"
        f"Encrypt={encrypt};"
        f"TrustServerCertificate={trust_cert};"
        "Connection Timeout=15;"
    )


def _is_transient_db_error(exc: BaseException) -> bool:
    """Identifies transient connection/network errors eligible for retry."""
    if pyodbc is not None and isinstance(exc, (pyodbc.OperationalError, pyodbc.DatabaseError)):
        return True
    return isinstance(exc, (ConnectionError, TimeoutError, OSError))


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=2.0),
    retry=retry_if_exception(_is_transient_db_error),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _create_raw_connection(conn_str: str):
    """Creates a raw pyodbc connection with exponential backoff on transient errors."""
    if pyodbc is None:
        raise RuntimeError("The 'pyodbc' package is not installed.")
    return pyodbc.connect(conn_str)


@contextmanager
def get_db_connection():
    """
    Context manager providing a managed database connection with automatic commit/rollback.
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
        logger.error("Database connection or execution failed: %s", _sanitize_log_message(ex))
        raise
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def execute_one(sql: str, params: Optional[Union[Tuple, List]] = None) -> Optional[Dict[str, Any]]:
    """
    Executes a parameterized query and returns the first row as a dictionary, or None.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, tuple(params or ()))
        columns = [column[0] for column in cursor.description] if cursor.description else []
        row = cursor.fetchone()
        cursor.close()
        if not row:
            return None
        return dict(zip(columns, row))


def execute_query(sql: str, params: Optional[Union[Tuple, List]] = None) -> List[Dict[str, Any]]:
    """
    Executes a parameterized SELECT query and returns rows as a list of dictionaries.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, tuple(params or ()))
        columns = [column[0] for column in cursor.description] if cursor.description else []
        rows = cursor.fetchall()
        cursor.close()
        return [dict(zip(columns, row)) for row in rows]


def execute_scalar(sql: str, params: Optional[Union[Tuple, List]] = None) -> Any:
    """
    Executes a parameterized query returning a single scalar value.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, tuple(params or ()))
        row = cursor.fetchone()
        cursor.close()
        return row[0] if row else None


def execute_non_query(sql: str, params: Optional[Union[Tuple, List]] = None) -> int:
    """
    Executes a parameterized INSERT, UPDATE, or DELETE query and returns rows affected.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, tuple(params or ()))
        rowcount = cursor.rowcount
        cursor.close()
        return rowcount
