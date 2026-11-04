#!/usr/bin/env python3
"""
Database Migration and Seeding Script for Azure Student Fee Management System.
Connects to SQL Server via pyodbc, executes database/schema.sql, seed.sql,
and seed_5000.sql in order (splitting on 'GO' lines), and prints Students row count.
"""

import os
import sys
import re

# Determine project root directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
DATABASE_DIR = os.path.join(ROOT_DIR, "database")


def load_env():
    """Load configuration from .env in project root."""
    env_path = os.path.join(ROOT_DIR, ".env")
    if not os.path.exists(env_path):
        print(f"[WARN] No .env file found at {env_path}. Looking in system environment...")
        return

    # Try python-dotenv if available
    try:
        from dotenv import load_dotenv
        load_dotenv(env_path)
        return
    except ImportError:
        pass

    # Fallback line-by-line .env parser
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip("'\"")
                if key not in os.environ:
                    os.environ[key] = val


def get_best_odbc_driver(pyodbc_module) -> str:
    available_drivers = pyodbc_module.drivers()

    preferred_drivers = [
        "ODBC Driver 18 for SQL Server",
        "ODBC Driver 17 for SQL Server"
    ]

    for driver in preferred_drivers:
        if driver in available_drivers:
            return driver

    raise RuntimeError(
        "Microsoft ODBC Driver 17 or 18 is required. "
        f"Available drivers: {available_drivers}"
    )


def split_sql_batches(sql_content: str) -> list:
    """
    Splits SQL script content into batches on lines containing only 'GO'
    (case-insensitive, ignoring leading/trailing whitespace).
    """
    batches = []
    current_batch = []

    for line in sql_content.splitlines():
        # Match lines that contain only 'GO' (ignoring whitespace and optional inline comments)
        stripped = line.strip()
        if re.match(r"^GO\s*(?:--.*)?$", stripped, re.IGNORECASE):
            batch_str = "\n".join(current_batch).strip()
            if batch_str:
                batches.append(batch_str)
            current_batch = []
        else:
            current_batch.append(line)

    # Append any remaining statements after the last GO
    remainder = "\n".join(current_batch).strip()
    if remainder:
        batches.append(remainder)

    return batches


def main():
    load_env()

    # Import pyodbc
    try:
        import pyodbc
    except ImportError:
        print("[ERROR] 'pyodbc' is not installed in the current Python environment.")
        print("Please install dependencies using: pip install pyodbc (or pip install -r functions/requirements.txt)")
        sys.exit(1)

    # Read connection credentials
    sa_password = os.environ.get("MSSQL_SA_PASSWORD") or os.environ.get("DB_PASSWORD")
    if not sa_password:
        print("[ERROR] MSSQL_SA_PASSWORD is not set in .env or environment variables.")
        sys.exit(1)

    server = os.environ.get("DB_SERVER", "localhost,1433")
    user = os.environ.get("DB_USER", "sa")
    driver = get_best_odbc_driver(pyodbc)

    print("=" * 60)
    print("Azure Student Fee Management - Database Migration Runner")
    print("=" * 60)
    print(f"Target Server : {server}")
    print(f"Database User : {user}")
    print(f"ODBC Driver   : {driver}")
    print("=" * 60)

    # Connect initially to 'master' so database creation scripts can execute
    conn_str = (
        f"Driver={{{driver}}};"
        f"Server={server};"
        f"Database=master;"
        f"Uid={user};"
        f"Pwd={sa_password};"
        f"TrustServerCertificate=yes;"
        f"Encrypt=yes;"
        "Connection Timeout=30;"
    )

    try:
        print("[1/4] Connecting to SQL Server...")
        conn = pyodbc.connect(conn_str, autocommit=True)
        cursor = conn.cursor()
        print("  -> Connected successfully.")
    except Exception as ex:
        print(f"[ERROR] Failed to connect to SQL Server: {ex}")
        sys.exit(1)

    # Files to execute in exact order
    files_to_run = ["schema.sql", "seed.sql", "seed_5000.sql"]

    for idx, filename in enumerate(files_to_run, start=2):
        file_path = os.path.join(DATABASE_DIR, filename)
        if not os.path.exists(file_path):
            print(f"[ERROR] Expected file not found: {file_path}")
            sys.exit(1)

        print(f"\n[{idx}/4] Executing: {filename}...")
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        batches = split_sql_batches(content)
        print(f"  -> Found {len(batches)} batch(es) separated by 'GO'.")

        for b_idx, batch in enumerate(batches, start=1):
            try:
                cursor.execute(batch)
            except Exception as ex:
                print(f"\n[ERROR] Execution failed in {filename} (batch #{b_idx}):")
                print(f"Statement preview: {batch[:200]}...")
                print(f"SQL Error: {ex}")
                cursor.close()
                conn.close()
                sys.exit(1)

        print(f"  -> Finished executing {filename}.")

    # Verify and print row count for Students table
    print("\n" + "=" * 60)
    print("Verification & Row Count")
    print("=" * 60)

    try:
        db_name = os.environ.get("DB_NAME", "FeeManagement")
        cursor.execute(f"USE [{db_name}];")
        cursor.execute("SELECT COUNT(*) FROM dbo.Students;")
        student_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM dbo.Administrators;")
        admin_count = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) 
            FROM dbo.Students 
            WHERE DueDate < CAST(GETDATE() AS DATE) AND PaidAmount < TotalFee;
        """)
        overdue_count = cursor.fetchone()[0]

        print(f"[SUCCESS] Total Students count       : {student_count:,}")
        print(f"[SUCCESS] Total Administrators count : {admin_count:,}")
        print(f"[SUCCESS] Total Overdue Students     : {overdue_count:,}")
    except Exception as ex:
        print(f"[ERROR] Could not fetch row counts: {ex}")
    finally:
        cursor.close()
        conn.close()

    print("=" * 60)
    print("All database migrations and seed scripts completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()

