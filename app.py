from fastapi import FastAPI, Request, Form, BackgroundTasks, Depends, HTTPException, status, File, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, Response, JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from datetime import datetime
from zoneinfo import ZoneInfo
from contextlib import contextmanager
import pandas as pd
import sqlite3
import requests
import time
import os
from pydantic_settings import BaseSettings

def get_current_time_str(format_str="%Y-%m-%d %H:%M:%S"):
    try:
        return datetime.now(ZoneInfo("Asia/Kolkata")).strftime(format_str)
    except Exception:
        return datetime.now().strftime(format_str)

class Settings(BaseSettings):
    AUTH_ID: str = "SA_OBPZVF0E"
    AUTH_TOKEN: str = "xczGOPgZi3TFCk7YMRDEsmU3vsD3xn8TSkGEOmOrNILzj8hbXMtOUvR79rVyP4KN"
    DATABASE_URL: str = "contacts.db"
    CALLER_ID: str = "+918065481889"
    ANSWER_URL: str = "https://file-deposit-image-proceeding.trycloudflare.com/answer"

    model_config = {"env_file": ".env", "extra": "ignore"}

os.makedirs("uploads", exist_ok=True)
os.makedirs("reports", exist_ok=True)
os.makedirs("audio", exist_ok=True)
os.makedirs("static", exist_ok=True)

settings = Settings()

app = FastAPI(title="Menmozhi AI Call Campaign System")

import json
from urllib.parse import quote, unquote
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from auth_utils import get_current_user_id
from app_auth import router as auth_router
from app_ai import ai_router

security = HTTPBearer(auto_error=False)

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user_id = get_current_user_id(credentials.credentials)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user_id

app.include_router(auth_router)
app.include_router(ai_router)

@app.get("/api/me")
def api_me(user_id: int = Depends(get_current_user)):
    with get_db_conn() as conn:
        user = conn.execute("SELECT id, username, email FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return dict(user)

def set_flash(response: Response, message: str, category: str = "info"):
    flash_data = {"message": message, "category": category}
    response.set_cookie(key="flash_msg", value=quote(json.dumps(flash_data)), max_age=10)

def get_flashed_messages(request: Request):
    flash_cookie = request.cookies.get("flash_msg")
    if flash_cookie:
        try:
            flash_data = json.loads(unquote(flash_cookie))
            return [(flash_data["category"], flash_data["message"])]
        except:
            return []
    return []

def clear_flash(response: Response):
    response.delete_cookie("flash_msg")

templates = Jinja2Templates(directory="templates")
templates.env.globals['get_flashed_messages'] = get_flashed_messages

@app.on_event("startup")
def on_startup():
    from database import init_db
    init_db(settings.DATABASE_URL)
    
    from auth_utils import get_password_hash
    with get_db_conn() as conn:
        cursor = conn.cursor()
        guest = cursor.execute("SELECT id FROM users WHERE username='guest'").fetchone()
        if not guest:
            cursor.execute(
                "INSERT INTO users (username, email, password_hash, is_verified) VALUES (?, ?, ?, ?)",
                ("guest", "guest@menmozhi.com", get_password_hash("guestpassword"), True)
            )
            conn.commit()
            
    print(f"[SUCCESS] App started.")

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
        df = pd.read_excel(file.file, header=None).fillna("")
        df = df.astype(str)
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": f"Invalid Excel file: {str(e)}"})
    contacts_to_insert = []
    for i in range(len(df)):
        row = df.iloc[i]
        if len(row) < 2: continue
        name = str(row[0]).strip()
        phone = "".join(filter(str.isdigit, str(row[1])))
        if name.lower() in ["nan", "name", "a1", "b1", ""]: continue
        if name == "" or phone == "": continue
        if len(phone) > 10: phone = phone[-10:]
        if len(phone) < 10: continue
        contacts_to_insert.append((name, phone))
    if contacts_to_insert:
        with get_db_conn() as conn:
            conn.executemany("INSERT OR IGNORE INTO contacts (name, phone) VALUES (?, ?)", contacts_to_insert)
            conn.commit()
    return RedirectResponse(url="/", status_code=303)

# =========================
# SINGLE CALL
# =========================
@app.get("/call/{contact_id}")
def call_contact(contact_id: int):
    with get_db_conn() as conn:
        contact = conn.execute("SELECT name, phone FROM contacts WHERE id=?", (contact_id,)).fetchone()
    if not contact: return JSONResponse(status_code=404, content={"status": "error", "message": "Contact not found"})
    name, phone = contact["name"], contact["phone"]
    url = f"https://api.vobiz.ai/api/v1/Account/{settings.AUTH_ID}/Call"
    headers = {"Content-Type": "application/json", "X-Auth-ID": settings.AUTH_ID, "X-Auth-Token": settings.AUTH_TOKEN}
    payload = {"from": settings.CALLER_ID, "to": f"+91{phone}", "answer_url": settings.ANSWER_URL}
    try:
        response = requests.post(url=url, headers=headers, json=payload, timeout=30)
        data = response.json()
    except requests.exceptions.JSONDecodeError:
        data = {"response": response.text}
    except Exception as e:
        data = {"error": str(e)}
    with get_db_conn() as conn:
        conn.execute("INSERT INTO call_api_logs (name, phone, api_response, created_at) VALUES (?, ?, ?, ?)", (name, phone, str(data), get_current_time_str()))
        conn.execute("INSERT INTO call_logs (name, phone, status, call_time) VALUES (?, ?, 'NO RESPONSE', ?)", (name, phone, get_current_time_str()))
        conn.commit()
    return JSONResponse(content={"status": "success", "message": f"Call initiated to {name}"})

# =========================
# CALL ALL (Background Task)
# =========================
def run_call_campaign(contacts_data: list):
    for contact in contacts_data:
        name, phone = contact["name"], str(contact["phone"]).strip()
        url = f"https://api.vobiz.ai/api/v1/Account/{settings.AUTH_ID}/Call"
        headers = {"Content-Type": "application/json", "X-Auth-ID": settings.AUTH_ID, "X-Auth-Token": settings.AUTH_TOKEN}
        payload = {"from": settings.CALLER_ID, "to": f"+91{phone}", "answer_url": settings.ANSWER_URL}
        try:
            response = requests.post(url=url, headers=headers, json=payload, timeout=30)
            with get_db_conn() as conn:
                conn.execute("INSERT INTO call_api_logs (name, phone, api_response, created_at) VALUES (?, ?, ?, ?)", (name, phone, str(response.text), get_current_time_str()))
                conn.execute("INSERT INTO call_logs (name, phone, status, call_time) VALUES (?, ?, 'NO RESPONSE', ?)", (name, phone, get_current_time_str()))
                conn.commit()
        except Exception:
            pass
        time.sleep(10)

@app.get("/call-all")
def call_all(background_tasks: BackgroundTasks):
    with get_db_conn() as conn:
        rows = conn.execute("SELECT id, name, phone FROM contacts").fetchall()
        contacts_data = [{"id": r["id"], "name": r["name"], "phone": r["phone"]} for r in rows]
    if not contacts_data: return JSONResponse(status_code=400, content={"status": "error", "message": "No contacts found"})
    background_tasks.add_task(run_call_campaign, contacts_data)
    return JSONResponse(content={"status": "success", "message": "Call campaign started"})

# =========================
# ANSWER (Vobiz fetches this)
# =========================
@app.api_route("/answer", methods=["GET", "POST"])
async def answer(request: Request):
    try:
        dtmf_url = str(request.url_for("dtmf_handler")).replace("http://", "https://")
    except:
        dtmf_url = settings.ANSWER_URL.replace('/answer', '/dtmf')
    xml = f"""<Response>
<GetDigits action="{dtmf_url}" method="POST" numDigits="1" timeout="10">
<Speak>Hello. This is Menmozhi Technologies. If you are available, please press 1. If not, press 0.</Speak>
</GetDigits>
<Speak>No response received.</Speak>
</Response>"""
    return Response(content=xml, media_type="application/xml")

# =========================
# DTMF HANDLER
# =========================
@app.post("/dtmf")
async def dtmf_handler(request: Request):
    try: form_data = dict(await request.form())
    except: form_data = {}
    if not form_data:
        try: form_data = await request.json()
        except: form_data = {}
    Digits = str(form_data.get("Digits") or form_data.get("digits") or "")
    to_number = str(form_data.get("To") or form_data.get("to") or form_data.get("Called") or "").strip()
    to_number = "".join(filter(str.isdigit, to_number))
    if len(to_number) > 10: to_number = to_number[-10:]
    status_val = "NO RESPONSE"
    if Digits == "1": status_val = "AVAILABLE"
    elif Digits == "0": status_val = "NOT AVAILABLE"
    if to_number:
        with get_db_conn() as conn:
            result = conn.execute("SELECT name FROM contacts WHERE phone=?", (to_number,)).fetchone()
            name = result["name"] if result else "Unknown"
            latest = conn.execute("SELECT id FROM call_logs WHERE phone=? AND status='NO RESPONSE' ORDER BY id DESC LIMIT 1", (to_number,)).fetchone()
            if latest:
                conn.execute("UPDATE call_logs SET status=?, call_time=? WHERE id=?", (status_val, get_current_time_str(), latest["id"]))
            else:
                conn.execute("INSERT INTO call_logs (name, phone, status, call_time) VALUES (?, ?, ?, ?)", (name, to_number, status_val, get_current_time_str()))
            conn.commit()
    return Response(content="<Response><Speak>Thank you.</Speak></Response>", media_type="application/xml")

# =========================
# VIEW LOGS / EXPORT / DELETE
# =========================
@app.get("/api/logs")
def get_logs(user_id: int = Depends(get_current_user)):
    with get_db_conn() as conn:
        data = conn.execute("SELECT * FROM call_logs ORDER BY id DESC").fetchall()
    return {"logs": [dict(row) for row in data]}

@app.get("/export-logs")
def export_logs():
    with get_db_conn() as conn:
        df = pd.read_sql_query("SELECT * FROM call_logs", conn)
    file_name = f"reports/call_logs_{get_current_time_str('%Y%m%d_%H%M%S')}.xlsx"
    df.to_excel(file_name, index=False)
    return FileResponse(path=file_name, filename=os.path.basename(file_name))

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

@app.get("/api/stats")
def get_stats(user_id: int = Depends(get_current_user)):
    with get_db_conn() as conn:
        total_contacts = conn.execute("SELECT COUNT(*) as count FROM contacts").fetchone()["count"]
        total_calls    = conn.execute("SELECT COUNT(*) as count FROM call_logs").fetchone()["count"]
        available      = conn.execute("SELECT COUNT(*) as count FROM call_logs WHERE status='AVAILABLE'").fetchone()["count"]
        not_available  = conn.execute("SELECT COUNT(*) as count FROM call_logs WHERE status='NOT AVAILABLE'").fetchone()["count"]
        no_response    = conn.execute("SELECT COUNT(*) as count FROM call_logs WHERE status='NO RESPONSE'").fetchone()["count"]
    return {
        "total_contacts": total_contacts, "total_calls": total_calls, "available": available,
        "not_available": not_available, "no_response": no_response,
        "success_rate": round((available / total_calls * 100), 1) if total_calls > 0 else 0
    }

@app.get("/api/contacts")
def api_contacts():
    with get_db_conn() as conn:
        contacts = conn.execute("SELECT * FROM contacts").fetchall()
    return {"contacts": [dict(row) for row in contacts]}

@app.get("/api-call-logs")
def api_call_logs():
    with get_db_conn() as conn:
        logs = conn.execute("SELECT * FROM call_api_logs ORDER BY id DESC").fetchall()
    return {"logs": [dict(row) for row in logs]}