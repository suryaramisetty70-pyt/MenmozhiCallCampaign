import sqlite3
import os
import re

try:
    import psycopg2
    import psycopg2.extras
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

class DBProxyCursor:
    def __init__(self, cursor, is_postgres):
        self.cursor = cursor
        self.is_postgres = is_postgres

    def _translate_query(self, query):
        if self.is_postgres:
            return query.replace("?", "%s")
        return query

    def execute(self, query, params=None):
        if params is None:
            self.cursor.execute(self._translate_query(query))
        else:
            self.cursor.execute(self._translate_query(query), params)
        return self

    def fetchone(self):
        res = self.cursor.fetchone()
        if res is not None and self.is_postgres:
            return dict(res)
        return res

    def fetchall(self):
        res = self.cursor.fetchall()
        if res is not None and self.is_postgres:
            return [dict(r) for r in res]
        return res

    @property
    def lastrowid(self):
        if self.is_postgres:
            try:
                self.cursor.execute("SELECT lastval()")
                return self.cursor.fetchone()[0]
            except Exception:
                return None
        return self.cursor.lastrowid

class DBProxyConnection:
    def __init__(self, db_url):
        self.is_postgres = db_url.startswith("postgres://") or db_url.startswith("postgresql://")
        if self.is_postgres:
            if not PSYCOPG2_AVAILABLE:
                raise RuntimeError("psycopg2-binary is required for PostgreSQL. Please install it.")
            self.conn = psycopg2.connect(db_url)
        else:
            self.conn = sqlite3.connect(db_url)
            self.conn.row_factory = sqlite3.Row

    def cursor(self):
        if self.is_postgres:
            cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        else:
            cur = self.conn.cursor()
        return DBProxyCursor(cur, self.is_postgres)

    def execute(self, query, params=None):
        cur = self.cursor()
        return cur.execute(query, params)

    def executemany(self, query, params_list):
        if self.is_postgres:
            cur = self.conn.cursor()
            psycopg2.extras.execute_batch(cur, query.replace("?", "%s"), params_list)
        else:
            cur = self.conn.cursor()
            cur.executemany(query, params_list)
        return self

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()

def get_connection(db_url="contacts.db"):
    return DBProxyConnection(db_url)

def init_db(db_url="contacts.db"):
    conn = get_connection(db_url)
    cursor = conn.cursor()

    def create_table(query):
        if conn.is_postgres:
            query = query.replace("AUTOINCREMENT", "")
            query = query.replace("INTEGER PRIMARY KEY", "SERIAL PRIMARY KEY")
            query = query.replace("BOOLEAN DEFAULT FALSE", "BOOLEAN DEFAULT FALSE")
        cursor.execute(query)

    try:
        cursor.execute("SELECT first_name FROM users LIMIT 1")
    except Exception:
        cursor.execute("DROP TABLE IF EXISTS users")
        conn.commit()
        
    try:
        cursor.execute("SELECT is_admin FROM users LIMIT 1")
    except Exception:
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT FALSE")
            conn.commit()
        except Exception:
            pass

    create_table("""
    CREATE TABLE IF NOT EXISTS contacts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        phone TEXT
    )
    """)

    create_table("""
    CREATE TABLE IF NOT EXISTS call_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        phone TEXT,
        status TEXT,
        call_time TEXT
    )
    """)

    create_table("""
    CREATE TABLE IF NOT EXISTS call_api_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        phone TEXT,
        api_response TEXT,
        created_at TEXT
    )
    """)

    create_table("""
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
        locked_until TEXT,
        is_admin BOOLEAN DEFAULT FALSE
    )
    """)

    create_table("""
    CREATE TABLE IF NOT EXISTS otp_verifications (
        email TEXT PRIMARY KEY,
        otp_secret TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        user_id INTEGER NOT NULL
    )
    """)

    create_table("""
    CREATE TABLE IF NOT EXISTS password_reset_tokens (
        token TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        expires_at TEXT NOT NULL
    )
    """)

    create_table("""
    CREATE TABLE IF NOT EXISTS ivr_scripts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        content TEXT NOT NULL,
        is_active BOOLEAN DEFAULT FALSE
    )
    """)

    conn.commit()
    
    # Insert default IVR script if none exists
    if not cursor.execute("SELECT id FROM ivr_scripts").fetchone():
        cursor.execute(
            "INSERT INTO ivr_scripts (name, content, is_active) VALUES (?, ?, ?)",
            ("Default Campaign", "Hello. This is Menmozhi Technologies. If you are available, please press 1. If not, press 0.", True)
        )
        conn.commit()

    conn.close()
    print("Database Ready — All tables verified.")

if __name__ == "__main__":
    init_db()