import sqlite3
import os

def init_db(db_path="contacts.db"):
    """Initialize all database tables. Safe to call multiple times."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

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

    conn.commit()
    conn.close()
    print("Database Ready — All tables verified.")

if __name__ == "__main__":
    init_db()