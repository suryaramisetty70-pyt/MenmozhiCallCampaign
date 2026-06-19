from fastapi import FastAPI, Request, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import FileResponse, RedirectResponse, Response, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from datetime import datetime
from contextlib import contextmanager
import pandas as pd
import sqlite3
import requests
import time
import os
import json

# --- Pydantic Settings (v1 / v2 compatible) ---
try:
    from pydantic_settings import BaseSettings
except ImportError:
    try:
        from pydantic import BaseSettings
    except ImportError:
        # Fallback: plain class if neither works
        class BaseSettings:
            def __init__(self, **kwargs):
                for k, v in kwargs.items():
                    setattr(self, k, v)

class Settings(BaseSettings):
    AUTH_ID: str = "SA_OBPZVF0E"
    AUTH_TOKEN: str = "3wiGGYBhqNDgxKJz72vP5R0YILOuxhsWU7Ka0orDR6GuO2PXtWBcZv6JA7CqJh8S"
    DATABASE_URL: str = "contacts.db"
    CALLER_ID: str = "+918065481889"
    ANSWER_URL: str = "https://menmozhicallcampaign-1.onrender.com/answer"

    class Config:
        env_file = ".env"

# Create required directories before mounting StaticFiles
os.makedirs("uploads", exist_ok=True)
os.makedirs("reports", exist_ok=True)
os.makedirs("audio", exist_ok=True)
os.makedirs("static", exist_ok=True)

settings = Settings()

app = FastAPI(title="Menmozhi AI Call Campaign System")

# Mount static directories
app.mount("/audio", StaticFiles(directory="audio"), name="audio")
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")


# --- Startup: Create directories and DB tables ---
@app.on_event("startup")
def on_startup():
    from database import init_db
    init_db(settings.DATABASE_URL)
    print("[SUCCESS] Application started. All tables and directories ready.")


# --- Database Helper ---
@contextmanager
def get_db_conn():
    conn = sqlite3.connect(settings.DATABASE_URL)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


# =========================
# DASHBOARD PAGE
# =========================
@app.get("/")
def dashboard(request: Request):
    with get_db_conn() as conn:
        cursor = conn.cursor()
        contacts = cursor.execute("SELECT * FROM contacts").fetchall()
        logs = cursor.execute("SELECT * FROM call_logs ORDER BY id DESC").fetchall()
        available_logs = cursor.execute("SELECT * FROM call_logs WHERE status='AVAILABLE' ORDER BY id DESC").fetchall()
        not_available_logs = cursor.execute("SELECT * FROM call_logs WHERE status='NOT AVAILABLE' ORDER BY id DESC").fetchall()
        no_response_logs = cursor.execute("SELECT * FROM call_logs WHERE status='NO RESPONSE' ORDER BY id DESC").fetchall()

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
    try:
        df = pd.read_excel(file.file, header=None, dtype=str)
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": f"Invalid Excel file: {str(e)}"})

    contacts_to_insert = []
    inserted = 0

    for i in range(len(df)):
        row = df.iloc[i]

        if len(row) < 2:
            continue

        name = str(row[0]).strip()
        phone = ''.join(filter(str.isdigit, str(row[1])))

        if name.lower() in ["nan", "name", "a1", "b1", ""]:
            continue

        if name == "" or phone == "":
            continue

        # Normalize: keep only last 10 digits
        if len(phone) > 10:
            phone = phone[-10:]

        contacts_to_insert.append((name, phone))
        inserted += 1

    if contacts_to_insert:
        with get_db_conn() as conn:
            conn.executemany("INSERT INTO contacts (name, phone) VALUES (?, ?)", contacts_to_insert)
            conn.commit()

    print(f"[SUCCESS] Inserted {inserted} contacts from Excel upload")
    return RedirectResponse(url="/", status_code=303)


# =========================
# SINGLE CALL
# =========================
@app.get("/call/{contact_id}")
def call_contact(contact_id: int):
    with get_db_conn() as conn:
        contact = conn.execute("SELECT name, phone FROM contacts WHERE id=?", (contact_id,)).fetchone()

    if not contact:
        return RedirectResponse(url="/", status_code=303)

    name = contact["name"]
    phone = contact["phone"]

    url = f"https://api.vobiz.ai/api/v1/Account/{settings.AUTH_ID}/Call"

    headers = {
        "Content-Type": "application/json",
        "X-Auth-ID": settings.AUTH_ID,
        "X-Auth-Token": settings.AUTH_TOKEN
    }

    payload = {
        "from": settings.CALLER_ID,
        "to": f"+91{phone}",
        "answer_url": settings.ANSWER_URL
    }

    try:
        response = requests.post(url=url, headers=headers, json=payload, timeout=30)
        data = response.json()
    except requests.exceptions.JSONDecodeError:
        data = {"response": response.text}
    except Exception as e:
        data = {"error": str(e)}

    print("VOBIZ API RESPONSE:", data)

    with get_db_conn() as conn:
        conn.execute("""
        INSERT INTO call_api_logs (name, phone, api_response, created_at)
        VALUES (?, ?, ?, ?)
        """, (name, phone, str(data), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

        conn.execute("""
        INSERT INTO call_logs (name, phone, status, call_time)
        VALUES (?, ?, 'NO RESPONSE', ?)
        """, (name, phone, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()

    return RedirectResponse(url="/", status_code=303)


# =========================
# CALL ALL (Background Task)
# =========================
def run_call_campaign(contacts_data: list):
    """
    Runs in a background thread.
    contacts_data is a list of plain dicts (not sqlite3.Row) for thread safety.
    """
    total = 0
    for contact in contacts_data:
        name = contact["name"]
        phone = str(contact["phone"]).strip()

        url = f"https://api.vobiz.ai/api/v1/Account/{settings.AUTH_ID}/Call"

        headers = {
            "Content-Type": "application/json",
            "X-Auth-ID": settings.AUTH_ID,
            "X-Auth-Token": settings.AUTH_TOKEN
        }

        payload = {
            "from": settings.CALLER_ID,
            "to": f"+91{phone}",
            "answer_url": settings.ANSWER_URL
        }

        try:
            print(f"[CALL] Calling {name} at {phone}...")
            response = requests.post(url=url, headers=headers, json=payload, timeout=30)

            with get_db_conn() as conn:
                conn.execute("""
                INSERT INTO call_api_logs (name, phone, api_response, created_at)
                VALUES (?, ?, ?, ?)
                """, (name, phone, str(response.text), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

                conn.execute("""
                INSERT INTO call_logs (name, phone, status, call_time)
                VALUES (?, ?, 'NO RESPONSE', ?)
                """, (name, phone, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                conn.commit()

            total += 1
        except Exception as e:
            print(f"[ERROR] CALL ERROR for {name}: {e}")

        time.sleep(20)

    print(f"[SUCCESS] Campaign finished. {total} calls initiated.")

@app.get("/call-all")
def call_all(background_tasks: BackgroundTasks):
    with get_db_conn() as conn:
        rows = conn.execute("SELECT id, name, phone FROM contacts").fetchall()
        # Convert to plain dicts for thread safety
        contacts_data = [{"id": r["id"], "name": r["name"], "phone": r["phone"]} for r in rows]

    if not contacts_data:
        return RedirectResponse(url="/", status_code=303)

    background_tasks.add_task(run_call_campaign, contacts_data)
    return RedirectResponse(url="/", status_code=303)


# =========================
# ANSWER (Vobiz fetches this)
# =========================
@app.api_route("/answer", methods=["GET", "POST"])
async def answer():
    xml = f"""
<Response>

<GetDigits
action="{settings.ANSWER_URL.replace('/answer', '/dtmf')}"
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
    return Response(content=xml, media_type="application/xml")


# =========================
# DTMF TEST
# =========================
@app.post("/dtmf-test")
async def dtmf_test(request: Request):
    form_data = await request.form()

    print("=== DTMF TEST HIT ===")
    for key, value in form_data.items():
        print(f"{key} = {value}")
    print("=====================")

    return Response(
        content="""
<Response>
    <Speak>
        Test successful. Thank you.
    </Speak>
</Response>
""",
        media_type="application/xml"
    )


# =========================
# DTMF HANDLER (stores 1=Available, 0=Not Available)
# =========================
@app.post("/dtmf")
async def dtmf_handler(request: Request):
    form_data = await request.form()

    print("=== FULL DTMF FORM DATA ===")
    for key, value in form_data.items():
        print(f"{key} = {value}")
    print("===========================")

    Digits = form_data.get("Digits") or form_data.get("digits") or ""

    to_number = (
        form_data.get("To") or
        form_data.get("to") or
        form_data.get("Called") or
        form_data.get("called") or
        "").strip()

    # Clean non-digits and keep only last 10 digits for robust matching
    to_number = ''.join(filter(str.isdigit, to_number))
    if len(to_number) > 10:
        to_number = to_number[-10:]

    print("DIGITS =", Digits)
    print("TO NUMBER =", to_number)

    status = "NO RESPONSE"
    if Digits == "1":
        status = "AVAILABLE"
    elif Digits == "0":
        status = "NOT AVAILABLE"

    if not to_number:
        print("[WARNING] DTMF received, but 'To' number is missing from webhook data.")
    else:
        with get_db_conn() as conn:
            result = conn.execute("SELECT name FROM contacts WHERE phone=?", (to_number,)).fetchone()
            name = result["name"] if result else "Unknown"

            print("NAME =", name)
            print("PHONE =", to_number)
            print("STATUS =", status)

            # FIX: Only update the LATEST 'NO RESPONSE' entry for this phone (not all)
            latest = conn.execute("""
            SELECT id FROM call_logs
            WHERE phone=? AND status='NO RESPONSE'
            ORDER BY id DESC LIMIT 1
            """, (to_number,)).fetchone()

            if latest:
                conn.execute("""
                UPDATE call_logs SET status=?, call_time=?
                WHERE id=?
                """, (status, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), latest["id"]))
            else:
                conn.execute("""
                INSERT INTO call_logs (name, phone, status, call_time)
                VALUES (?, ?, ?, ?)
                """, (name, to_number, status, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

            conn.commit()
            print("[SUCCESS] DATABASE SAVED SUCCESSFULLY")

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


# =========================
# VIEW LOGS
# =========================
@app.get("/logs")
def get_logs():
    with get_db_conn() as conn:
        data = conn.execute("SELECT * FROM call_logs ORDER BY id DESC").fetchall()
    return {"logs": [dict(row) for row in data]}


# =========================
# EXPORT LOGS TO EXCEL
# =========================
@app.get("/export-logs")
def export_logs():
    with get_db_conn() as conn:
        df = pd.read_sql_query("SELECT * FROM call_logs", conn)

    os.makedirs("reports", exist_ok=True)
    file_name = f"reports/call_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    df.to_excel(file_name, index=False)

    return FileResponse(path=file_name, filename=os.path.basename(file_name))


# =========================
# DELETE ENDPOINTS
# =========================
@app.get("/delete-contact/{contact_id}")
def delete_contact(contact_id: int):
    with get_db_conn() as conn:
        conn.execute("DELETE FROM contacts WHERE id=?", (contact_id,))
        conn.commit()
    return RedirectResponse(url="/", status_code=303)

@app.get("/delete-all-contacts")
def delete_all_contacts():
    with get_db_conn() as conn:
        conn.execute("DELETE FROM contacts")
        conn.commit()
    return RedirectResponse(url="/", status_code=303)

@app.get("/delete-all-logs")
def delete_all_logs():
    with get_db_conn() as conn:
        conn.execute("DELETE FROM call_logs")
        conn.commit()
    return RedirectResponse(url="/", status_code=303)


# =========================
# API ENDPOINTS
# =========================
@app.get("/api/stats")
def api_stats():
    with get_db_conn() as conn:
        total_contacts = conn.execute("SELECT COUNT(*) as count FROM contacts").fetchone()["count"]
        total_calls = conn.execute("SELECT COUNT(*) as count FROM call_logs").fetchone()["count"]
        available = conn.execute("SELECT COUNT(*) as count FROM call_logs WHERE status='AVAILABLE'").fetchone()["count"]
        not_available = conn.execute("SELECT COUNT(*) as count FROM call_logs WHERE status='NOT AVAILABLE'").fetchone()["count"]
        no_response = conn.execute("SELECT COUNT(*) as count FROM call_logs WHERE status='NO RESPONSE'").fetchone()["count"]

    return {
        "total_contacts": total_contacts,
        "total_calls": total_calls,
        "available": available,
        "not_available": not_available,
        "no_response": no_response,
        "success_rate": round((available / total_calls * 100), 1) if total_calls > 0 else 0
    }


@app.get("/api/contacts")
def api_contacts():
    with get_db_conn() as conn:
        contacts = conn.execute("SELECT * FROM contacts").fetchall()
    return {"contacts": [dict(row) for row in contacts]}


@app.get("/api/logs")
def api_logs():
    with get_db_conn() as conn:
        logs = conn.execute("SELECT * FROM call_logs ORDER BY id DESC").fetchall()
    return {"logs": [dict(row) for row in logs]}


@app.get("/api-call-logs")
def api_call_logs():
    with get_db_conn() as conn:
        logs = conn.execute("SELECT * FROM call_api_logs ORDER BY id DESC").fetchall()
    return {"logs": [dict(row) for row in logs]}