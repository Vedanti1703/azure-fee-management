"""
Database connection and query execution utilities for SQL Server / Azure SQL.
All configurations are read strictly from environment variables.
"""

import os
import logging
from typing import List, Dict, Any, Optional
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Optional import to allow unit tests and environments without native ODBC drivers
try:
    import pyodbc
except ImportError:
    pyodbc = None  # Handled gracefully with informative errors


def get_connection_string() -> str:
    """
    Constructs or retrieves the database connection string from environment variables.
    No hardcoded credentials allowed.
    """
    raw_conn_str = os.environ.get("AZURE_SQL_CONNECTIONSTRING")
    if raw_conn_str:
        return raw_conn_str

    server = os.environ.get("DB_SERVER", "localhost,1433")
    database = os.environ.get("DB_NAME", "StudentFeeManagementDB")
    user = os.environ.get("DB_USER", "sa")
    password = os.environ.get("DB_PASSWORD", "")
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
        "Connection Timeout=30;"
    )


@contextmanager
def get_db_connection():
    """
    Context manager yielding a pyodbc database connection with automatic commit/rollback.
    """
    if pyodbc is None:
        raise RuntimeError(
            "The 'pyodbc' library is not installed or available in this environment. "
            "Please ensure requirements.txt is installed and ODBC Driver is available."
        )

    conn_str = get_connection_string()
    conn = None
    try:
        conn = pyodbc.connect(conn_str)
        yield conn
        conn.commit()
    except Exception as ex:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        logger.error(f"Database error occurred: {str(ex)}")
        raise
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def execute_query(sql: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
    """
    Executes a SELECT query and returns rows as a list of dictionaries.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params or ())
        columns = [column[0] for column in cursor.description] if cursor.description else []
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]
        cursor.close()
        return results


def execute_scalar(sql: str, params: Optional[tuple] = None) -> Any:
    """
    Executes a query returning a single scalar value.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params or ())
        row = cursor.fetchone()
        cursor.close()
        return row[0] if row else None


def execute_non_query(sql: str, params: Optional[tuple] = None) -> int:
    """
    Executes an INSERT, UPDATE, or DELETE query and returns rows affected.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params or ())
        rowcount = cursor.rowcount
        cursor.close()
        return rowcount

