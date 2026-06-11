import sqlite3

conn = sqlite3.connect("contacts.db")
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

conn.commit()
conn.close()

print("Database Ready")