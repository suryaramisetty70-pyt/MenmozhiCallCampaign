import sqlite3

conn = sqlite3.connect("contacts.db")
cursor = conn.cursor()

cursor.execute("DELETE FROM contacts")

conn.commit()
conn.close()

print("Database cleaned successfully")