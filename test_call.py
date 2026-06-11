import requests

AUTH_ID = "SA_OBPZVF0E"
AUTH_TOKEN = "qCVCmUy0C2GkXGqo9jCMYFN6AOvx9gQZWf7QvlpUDSWcopIyGGywwnzPEHRziNWA"

url = f"https://api.vobiz.ai/api/v1/Account/{AUTH_ID}/Call"

headers = {
    "Content-Type": "application/json",
    "X-Auth-ID": AUTH_ID.strip(),
    "X-Auth-Token": AUTH_TOKEN.strip()
}
import sqlite3

conn = sqlite3.connect("contacts.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS current_call (
    id INTEGER PRIMARY KEY,
    name TEXT,
    phone TEXT
)
""")

cursor.execute("DELETE FROM current_call")

cursor.execute("""
INSERT INTO current_call
(name, phone)
VALUES (?, ?)
""",
(
    "surya",
    "9182169637"
))

conn.commit()
conn.close()

payload = {
    "from": "+918065481889",
    "to": "+919182169637",
    "answer_url": "https://mods-ringtone-menus-shut.trycloudflare.com?/answer"
}

print("Sending request...")

response = requests.post(
    url=url,
    headers=headers,
    json=payload,
    timeout=30
)

print("Status Code:", response.status_code)

data = response.json()

print("FULL RESPONSE:")
print(response.text)
print("Status Code:", response.status_code)

print("FULL RESPONSE:")
print(response.text)

if "request_uuid" in data:
    print("CALL UUID =", data["request_uuid"])