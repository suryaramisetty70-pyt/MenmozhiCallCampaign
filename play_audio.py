import requests

# =========================
# VOBIZ CREDENTIALS
# =========================

AUTH_ID = "SA_OBPZVF0E"
AUTH_TOKEN = "1952f7b35606a45c6b6ab8710b114d1d9502a6661af9458ba87e4c762e22b666"

# =========================
# CALL UUID
# =========================

CALL_UUID = "978fe0f3-144e-4fc8-a190-1821ffbd8f70"

# =========================
# PLAY AUDIO API URL
# =========================

url = f"https://api.vobiz.ai/api/v1/Account/{AUTH_ID}/Call/{CALL_UUID}/Play"

# =========================
# HEADERS
# =========================

headers = {
    "Content-Type": "application/json",
    "X-Auth-ID": AUTH_ID.strip(),
    "X-Auth-Token": AUTH_TOKEN.strip()
}

# =========================
# AUDIO FILE URL
# =========================

payload = {
    "urls": "https://tmpfiles.org/dl/wUwqZQFC6zrg/welcome.mp3",
    "legs": "aleg"
}

# =========================
# SEND REQUEST
# =========================

response = requests.post(
    url,
    headers=headers,
    json=payload
)

print("Status:", response.status_code)
print("Response:")
print(response.text)