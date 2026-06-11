from fastapi.responses import FileResponse
from fastapi import FastAPI, Request, UploadFile, File
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from datetime import datetime
import pandas as pd
import sqlite3

app = FastAPI()
from fastapi.staticfiles import StaticFiles

app.mount("/audio", StaticFiles(directory="audio"), name="audio")

templates = Jinja2Templates(directory="templates")


# =========================
# DASHBOARD PAGE
# =========================
@app.get("/")
def dashboard(request: Request):

    conn = sqlite3.connect("contacts.db")
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM contacts")
    contacts = cursor.fetchall()

    cursor.execute(
        "SELECT * FROM call_logs ORDER BY id DESC"
    )
    logs = cursor.fetchall()

    cursor.execute(
        "SELECT * FROM call_logs WHERE status='AVAILABLE' ORDER BY id DESC"
    )
    available_logs = cursor.fetchall()

    cursor.execute(
        "SELECT * FROM call_logs WHERE status='NOT AVAILABLE' ORDER BY id DESC"
    )
    not_available_logs = cursor.fetchall()

    cursor.execute(
        "SELECT * FROM call_logs WHERE status='NO RESPONSE' ORDER BY id DESC"
    )
    no_response_logs = cursor.fetchall()

    conn.close()

    return templates.TemplateResponse(
    request=request,
    name="index.html",
    context={
        "request": request,
        "contacts": contacts,
        "logs": logs,
        "available_logs": available_logs,
        "not_available_logs": not_available_logs,
        "no_response_logs": no_response_logs
    }
)
# =========================
# UPLOAD EXCEL
# =========================
@app.post("/upload")
async def upload_excel(file: UploadFile = File(...)):

    df = pd.read_excel(file.file, header=None)

    conn = sqlite3.connect("contacts.db")
    cursor = conn.cursor()

    inserted = 0

    for i in range(len(df)):

        row = df.iloc[i]

        if len(row) < 2:
            continue

        name = str(row[0]).strip()
        phone = str(row[1]).strip()

        if name.lower() in ["nan", "name", "a1", "b1"]:
            continue

        if phone.lower() in ["nan", "phone"]:
            continue

        if name == "" or phone == "":
            continue

        cursor.execute(
            "INSERT INTO contacts (name, phone) VALUES (?, ?)",
            (name, phone)
        )

        inserted += 1

    conn.commit()
    conn.close()

    print(f"Inserted {inserted} rows")

    return RedirectResponse(
        url="/",
        status_code=303
    )


# =========================
# SINGLE CALL
# =========================
@app.get("/call/{contact_id}")
def call_contact(contact_id: int):

    import requests
    import sqlite3

    AUTH_ID = "SA_OBPZVF0E"
    AUTH_TOKEN = "qCVCmUy0C2GkXGqo9jCMYFN6AOvx9gQZWf7QvlpUDSWcopIyGGywwnzPEHRziNWA"

    conn = sqlite3.connect("contacts.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT name, phone FROM contacts WHERE id=?",
        (contact_id,)
    )

    contact = cursor.fetchone()

    if not contact:
        conn.close()
        return {"message": "Contact not found"}

    name = contact[0]
    phone = contact[1]

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS current_call (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        name,
        phone
    ))

    conn.commit()
    conn.close()

    url = f"https://api.vobiz.ai/api/v1/Account/{AUTH_ID}/Call"

    headers = {
        "Content-Type": "application/json",
        "X-Auth-ID": AUTH_ID,
        "X-Auth-Token": AUTH_TOKEN
    }

    payload = {
        "from": "+918065481889",
        "to": f"+91{phone}",
       "answer_url": "https://mods-ringtone-menus-shut.trycloudflare.com?/answer"
    }

    response = requests.post(
        url=url,
        headers=headers,
        json=payload,
        timeout=30
    )

    try:
        data = response.json()
    except:
        data = {"response": response.text}

    return {
        "contact": name,
        "phone": phone,
        "vobiz_response": data
    }

# =========================
# CALL ALL (SIMULATION)
# =========================

@app.get("/call-all")
def call_all():

    import requests
    import sqlite3
    import time
    from datetime import datetime

    AUTH_ID = "SA_OBPZVF0E"
    AUTH_TOKEN = "qCVCmUy0C2GkXGqo9jCMYFN6AOvx9gQZWf7QvlpUDSWcopIyGGywwnzPEHRziNWA"

    conn = sqlite3.connect("contacts.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, name, phone FROM contacts"
    )

    contacts = cursor.fetchall()

    total = 0

    for contact in contacts:

        name = contact[1]
        phone = str(contact[2]).strip()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS current_call (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            name,
            phone
        ))

        conn.commit()

        url = f"https://api.vobiz.ai/api/v1/Account/{AUTH_ID}/Call"

        headers = {
            "Content-Type": "application/json",
            "X-Auth-ID": AUTH_ID,
            "X-Auth-Token": AUTH_TOKEN
        }

        payload = {
            "from": "+918065481889",
            "to": f"+91{phone}",
            "answer_url": "https://mods-ringtone-menus-shut.trycloudflare.com?/answer"
        }

        try:
            response = requests.post(
                url=url,
                headers=headers,
                json=payload,
                timeout=30
            )

            cursor.execute("""
            INSERT INTO call_logs
            (name, phone, status, call_time)
            VALUES (?, ?, ?, ?)
            """,
            (
                name,
                phone,
                "NO RESPONSE",
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ))

            conn.commit()

            total += 1

        except Exception as e:
            print("CALL ERROR:", e)

        time.sleep(20)

    conn.close()

    return {
        "message": f"{total} calls initiated"
    }

# =========================
# TEST LOG
# =========================
@app.get("/test-log")
def test_log():

    conn = sqlite3.connect("contacts.db")
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO call_logs
    (name, phone, status, call_time)
    VALUES (?, ?, ?, ?)
    """,
    (
        "surya",
        "9182169637",
        "COMPLETED",
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    conn.commit()
    conn.close()

    return {"message": "Log Added"}


# =========================
# VIEW LOGS
# =========================
@app.get("/logs")
def get_logs():

    conn = sqlite3.connect("contacts.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM call_logs ORDER BY id DESC"
    )

    data = cursor.fetchall()

    conn.close()

    return {
        "logs": data
    }
@app.get("/export-logs")
def export_logs():

    conn = sqlite3.connect("contacts.db")

    df = pd.read_sql_query(
        "SELECT * FROM call_logs",
        conn
    )

    conn.close()

    file_name = "call_logs.xlsx"

    df.to_excel(
        file_name,
        index=False
    )

    return FileResponse(
        path=file_name,
        filename=file_name
    )
from fastapi import Form
from fastapi.responses import Response


@app.api_route("/answer", methods=["GET", "POST"])
async def answer():

    xml = """
<Response>

<GetDigits
action="https://strengths-itunes-find-tub.trycloudflare.com/dtmf"
method="POST"
numDigits="1"
timeout="10">

<Speak>

Hello and thank you for taking our call.

This is Menmozhi Technologies Private Limited.

We would like to know your current availability.

If you are available to proceed, please press 1 now.

If you are currently unavailable, please press 0.

Thank you for your valuable time.

</Speak>

</GetDigits>

<Speak>
No response received.
</Speak>

</Response>
"""

    return Response(
        content=xml,
        media_type="application/xml"
    )


from fastapi import Form
from fastapi.responses import Response
from datetime import datetime
import sqlite3


@app.post("/dtmf")
async def dtmf_handler(Digits: str = Form(None)):

    print("KEY PRESSED =", Digits)

    status = "NO RESPONSE"

    if Digits == "1":
        status = "AVAILABLE"

    elif Digits == "0":
        status = "NOT AVAILABLE"

    # Get the last called contact
    conn2 = sqlite3.connect("contacts.db")
    cursor2 = conn2.cursor()

    cursor2.execute("""
    CREATE TABLE IF NOT EXISTS current_call (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        phone TEXT
    )
    """)

    cursor2.execute("""
    SELECT name, phone
    FROM current_call
    ORDER BY id DESC
    LIMIT 1
    """)

    contact = cursor2.fetchone()

    conn2.close()

    name = "Unknown"
    phone = "Unknown"

    if contact:
        name = contact[0]
        phone = contact[1]

    # Save response to call_logs
    conn = sqlite3.connect("contacts.db")
    cursor = conn.cursor()
    cursor.execute("""
DELETE FROM call_logs
WHERE phone=? AND status='NO RESPONSE'
""", (phone,))

    cursor.execute("""
    INSERT INTO call_logs
    (name, phone, status, call_time)
    VALUES (?, ?, ?, ?)
    """,
    (
        name,
        phone,
        status,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    conn.commit()
    conn.close()

    return Response(
        content="""
<Response>
    <Speak>
        Thank you for your response.
        Your availability has been recorded successfully.
    </Speak>
</Response>
""",
        media_type="application/xml"
    )
@app.get("/api/stats")
def api_stats():

    conn = sqlite3.connect("contacts.db")
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM contacts")
    total_contacts = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM call_logs")
    total_calls = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM call_logs WHERE status='AVAILABLE'")
    available = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM call_logs WHERE status='NOT AVAILABLE'")
    not_available = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM call_logs WHERE status='NO RESPONSE'")
    no_response = cursor.fetchone()[0]

    conn.close()

    return {
        "total_contacts": total_contacts,
        "total_calls": total_calls,
        "available": available,
        "not_available": not_available,
        "no_response": no_response
    }
@app.get("/api/contacts")
def api_contacts():

    conn = sqlite3.connect("contacts.db")
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM contacts")
    contacts = cursor.fetchall()

    conn.close()

    return {"contacts": contacts}


@app.get("/api/logs")
def api_logs():

    conn = sqlite3.connect("contacts.db")
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM call_logs ORDER BY id DESC")
    logs = cursor.fetchall()

    conn.close()

    return {"logs": logs}