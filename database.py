import sqlite3
import os

def init_db(db_path="contacts.db"):
    """Initialize all database tables. Safe to call multiple times."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # MIGRATION: Check if old users table exists without first_name
    try:
        cursor.execute("SELECT first_name FROM users LIMIT 1")
    except sqlite3.OperationalError:
        # If it fails, the table either doesn't exist or is the old schema.
        # Drop the old table so it can be recreated correctly.
        cursor.execute("DROP TABLE IF EXISTS users")


    cursor.execute("""
    CREATE TABLE IF NOT EXISTS contacts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        phone TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS call_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        phone TEXT,
        status TEXT,
        call_time TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS call_api_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        phone TEXT,
        api_response TEXT,
        created_at TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        first_name TEXT,
        last_name TEXT,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        is_verified BOOLEAN DEFAULT FALSE,
        created_at TEXT,
        last_login TEXT,
        failed_login_attempts INTEGER DEFAULT 0,
        locked_until TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS otp_verifications (
        email TEXT PRIMARY KEY,
        otp_secret TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        user_id INTEGER NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS password_reset_tokens (
        token TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        expires_at TEXT NOT NULL
    )
    """)

    conn.commit()
    conn.close()
    print("Database Ready — All tables verified.")

if __name__ == "__main__":
    init_db()