from fastapi import FastAPI, Request, UploadFile, File, Form, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import FileResponse, RedirectResponse, Response, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from contextlib import contextmanager
from passlib.context import CryptContext
from jose import JWTError, jwt
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import secrets
import pandas as pd
import sqlite3
import requests
import time
import os
import json

def get_current_time_str(format_str="%Y-%m-%d %H:%M:%S"):
    try:
        return datetime.now(ZoneInfo("Asia/Kolkata")).strftime(format_str)
    except Exception:
        return datetime.now().strftime(format_str)

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
    ANSWER_URL: str = "https://menmozhicallcampaign.onrender.com/answer"
    SMTP_EMAIL: str = "suryaramisetty70@gmail.com"
    SMTP_PASSWORD: str = "cutj qsnl zkqi fqlf"
    SECRET_KEY: str = "default_unsafe_secret_menmozhi_auth_key"

    class Config:
        env_file = ".env"

# Create required directories before mounting StaticFiles
os.makedirs("uploads", exist_ok=True)
os.makedirs("reports", exist_ok=True)
os.makedirs("audio", exist_ok=True)
os.makedirs("static", exist_ok=True)

settings = Settings()

from fastapi.responses import JSONResponse

app = FastAPI(title="Menmozhi AI Call Campaign System")

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    error_detail = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    print(error_detail)
    return JSONResponse(status_code=500, content={"status": "error", "message": f"Server Error: {str(exc)}"})

# =========================
# AUTHENTICATION LOGIC
# =========================
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

def get_password_hash(password):
    if not password:
        password = ""
    # Safe 71-byte truncation for bcrypt (leaving 1 byte for null terminator)
    safe_password = password.encode('utf-8')[:71].decode('utf-8', 'ignore')
    return pwd_context.hash(safe_password)

def verify_password(plain_password, hashed_password):
    if not plain_password:
        plain_password = ""
    safe_password = plain_password.encode('utf-8')[:71].decode('utf-8', 'ignore')
    return pwd_context.verify(safe_password, hashed_password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

otp_store = {}

def send_otp_email(to_email: str, otp: str):
    api_key_part1 = "xkeysib-7322cfe7a38e4a063926dfe1e"
    api_key_part2 = "1e635c1106737e1ffa9b25781ae1fe38d81f776-aH2tDcL2SlLsPCdh"
    api_key = api_key_part1 + api_key_part2
    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "accept": "application/json",
        "api-key": api_key,
        "content-type": "application/json"
    }
    data = {
        "sender": {"name": "Menmozhi Team", "email": "suryaramisetty70@gmail.com"},
        "to": [{"email": to_email}],
        "subject": "Menmozhi Campaign Engine - Your Verification Code",
        "textContent": f"Hello,\n\nYour OTP for registration is: {otp}\n\nThis code will expire in 10 minutes.\n\nRegards,\nMenmozhi Team"
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)
        if response.status_code in [200, 201, 202]:
            return True, "OTP sent successfully"
        else:
            error_msg = response.text
            print(f"[ERROR] Failed to send email via Brevo: {error_msg}")
            return False, error_msg
    except Exception as e:
        error_msg = str(e)
        print(f"[ERROR] Exception sending email via Brevo: {error_msg}")
        return False, error_msg

def get_current_user(request: Request):
    token = request.cookies.get("session_token")
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            return None
        with get_db_conn() as conn:
            user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        return user
    except JWTError:
        return None

def auth_required(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/login"}
        )
    return user

# Mount static directories
app.mount("/audio", StaticFiles(directory="audio"), name="audio")
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")


# --- Startup: Create directories and DB tables ---
@app.on_event("startup")
def on_startup():
    from database import init_db
    init_db(settings.DATABASE_URL)
    with get_db_conn() as conn:
        try:
            conn.execute("ALTER TABLE users ADD COLUMN username TEXT")
            conn.commit()
            print("[SUCCESS] Migrated users table (added username).")
        except Exception:
            pass  # Column already exists
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
# AUTHENTICATION ENDPOINTS
# =========================
@app.get("/login")
def login_page(request: Request):
    if get_current_user(request):
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(request=request, name="auth.html", context={})

@app.post("/api/auth/send-otp")
async def api_send_otp(request: Request):
    data = await request.json()
    email = data.get("email")
    if not email:
        return JSONResponse(status_code=400, content={"status": "error", "message": "Email is required"})
    
    with get_db_conn() as conn:
        user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if user:
            return JSONResponse(status_code=400, content={"status": "error", "message": "Email already registered"})
        
    otp = "".join([str(secrets.randbelow(10)) for _ in range(6)])
    expires_at = time.time() + 600  # 10 minutes
    
    otp_store[email] = {
        "otp": otp,
        "expires_at": expires_at
    }
    
    success, msg_detail = send_otp_email(email, otp)
    if success:
        return {"status": "success", "message": "OTP sent"}
    else:
        return JSONResponse(status_code=500, content={"status": "error", "message": f"Failed to send email: {msg_detail}"})

@app.post("/api/auth/signup")
async def api_signup(request: Request):
    try:
        data = await request.json()
        email = data.get("email")
        username = data.get("username")
        password = data.get("password")
        otp = data.get("otp")
        
        if not all([email, username, password, otp]):
            return JSONResponse(status_code=400, content={"status": "error", "message": "Missing fields"})
            
        otp_data = otp_store.get(email)
        if not otp_data or otp_data["otp"] != otp or time.time() > otp_data["expires_at"]:
            return JSONResponse(status_code=400, content={"status": "error", "message": "Invalid or expired OTP"})
            
        hashed_pw = get_password_hash(password)
        try:
            with get_db_conn() as conn:
                conn.execute("INSERT INTO users (email, username, password_hash, created_at) VALUES (?, ?, ?, ?)", 
                             (email, username, hashed_pw, get_current_time_str()))
                conn.commit()
            del otp_store[email]
        except sqlite3.IntegrityError:
            return JSONResponse(status_code=400, content={"status": "error", "message": "An account with this email already exists."})
            
        return {"status": "success", "message": "Account created successfully"}
    except Exception as e:
        import traceback
        err = traceback.format_exc()
        print("[SIGNUP ERROR]", err)
        return JSONResponse(status_code=500, content={"status": "error", "message": f"CRITICAL ERROR: {str(e)}"})

@app.post("/api/auth/login")
async def api_login(request: Request):
    try:
        data = await request.json()
        email = data.get("email")
        password = data.get("password")
        
        with get_db_conn() as conn:
            user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
            if not user or not verify_password(password, user["password_hash"]):
                return JSONResponse(status_code=401, content={"status": "error", "message": "Invalid credentials"})
                
        access_token = create_access_token(data={"sub": email})
        response = JSONResponse(content={"status": "success", "message": "Logged in"})
        response.set_cookie(key="session_token", value=access_token, httponly=True, max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60)
        return response
    except Exception as e:
        import traceback
        err = traceback.format_exc()
        print("[LOGIN ERROR]", err)
        return JSONResponse(status_code=500, content={"status": "error", "message": f"CRITICAL ERROR: {str(e)}"})

@app.get("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("session_token")
    return response


# =========================
# DASHBOARD PAGE
# =========================
@app.get("/")
def dashboard(request: Request):
    if not get_current_user(request):
        return RedirectResponse(url="/login", status_code=303)
        
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
async def upload_excel(file: UploadFile = File(...), user: dict = Depends(auth_required)):
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
def call_contact(contact_id: int, user: dict = Depends(auth_required)):
    with get_db_conn() as conn:
        contact = conn.execute("SELECT name, phone FROM contacts WHERE id=?", (contact_id,)).fetchone()

    if not contact:
        return JSONResponse(status_code=404, content={"status": "error", "message": "Contact not found"})

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
        """, (name, phone, str(data), get_current_time_str()))

        conn.execute("""
        INSERT INTO call_logs (name, phone, status, call_time)
        VALUES (?, ?, 'NO RESPONSE', ?)
        """, (name, phone, get_current_time_str()))
        conn.commit()

    return JSONResponse(content={"status": "success", "message": f"Call initiated to {name}"})


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
                """, (name, phone, str(response.text), get_current_time_str()))

                conn.execute("""
                INSERT INTO call_logs (name, phone, status, call_time)
                VALUES (?, ?, 'NO RESPONSE', ?)
                """, (name, phone, get_current_time_str()))
                conn.commit()

            total += 1
        except Exception as e:
            print(f"[ERROR] CALL ERROR for {name}: {e}")

        time.sleep(10)

    print(f"[SUCCESS] Campaign finished. {total} calls initiated.")

@app.get("/call-all")
def call_all(background_tasks: BackgroundTasks, user: dict = Depends(auth_required)):
    with get_db_conn() as conn:
        rows = conn.execute("SELECT id, name, phone FROM contacts").fetchall()
        # Convert to plain dicts for thread safety
        contacts_data = [{"id": r["id"], "name": r["name"], "phone": r["phone"]} for r in rows]

    if not contacts_data:
        return JSONResponse(status_code=400, content={"status": "error", "message": "No contacts found"})

    background_tasks.add_task(run_call_campaign, contacts_data)
    return JSONResponse(content={"status": "success", "message": "Call campaign started"})

# =========================
# POLLING ENDPOINT (AJAX)
# =========================
@app.get("/api/logs")
def api_get_logs(user: dict = Depends(auth_required)):
    with get_db_conn() as conn:
        data = conn.execute("SELECT * FROM call_logs ORDER BY id DESC").fetchall()
    return {"logs": [dict(row) for row in data]}


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
    try:
        form_data = dict(await request.form())
    except Exception:
        form_data = {}

    if not form_data:
        try:
            form_data = await request.json()
        except Exception:
            form_data = {}

    print("=== FULL DTMF DATA ===")
    for key, value in form_data.items():
        print(f"{key} = {value}")
    print("===========================")

    Digits = str(form_data.get("Digits") or form_data.get("digits") or "")

    to_number = str(
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
                """, (status, get_current_time_str(), latest["id"]))
            else:
                conn.execute("""
                INSERT INTO call_logs (name, phone, status, call_time)
                VALUES (?, ?, ?, ?)
                """, (name, to_number, status, get_current_time_str()))

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
def get_logs(user: dict = Depends(auth_required)):
    with get_db_conn() as conn:
        data = conn.execute("SELECT * FROM call_logs ORDER BY id DESC").fetchall()
    return {"logs": [dict(row) for row in data]}


# =========================
# EXPORT LOGS TO EXCEL
# =========================
@app.get("/export-logs")
def export_logs(user: dict = Depends(auth_required)):
    with get_db_conn() as conn:
        df = pd.read_sql_query("SELECT * FROM call_logs", conn)

    os.makedirs("reports", exist_ok=True)
    file_name = f"reports/call_logs_{get_current_time_str('%Y%m%d_%H%M%S')}.xlsx"
    df.to_excel(file_name, index=False)

    return FileResponse(path=file_name, filename=os.path.basename(file_name))


# =========================
# DELETE ENDPOINTS
# =========================
@app.get("/delete-contact/{contact_id}")
def delete_contact(contact_id: int, user: dict = Depends(auth_required)):
    with get_db_conn() as conn:
        conn.execute("DELETE FROM contacts WHERE id=?", (contact_id,))
        conn.commit()
    return RedirectResponse(url="/", status_code=303)

@app.get("/delete-all-contacts")
def delete_all_contacts(user: dict = Depends(auth_required)):
    with get_db_conn() as conn:
        conn.execute("DELETE FROM contacts")
        conn.commit()
    return RedirectResponse(url="/", status_code=303)

@app.get("/delete-all-logs")
def delete_all_logs(user: dict = Depends(auth_required)):
    with get_db_conn() as conn:
        conn.execute("DELETE FROM call_logs")
        conn.commit()
    return RedirectResponse(url="/", status_code=303)


# =========================
# API ENDPOINTS
# =========================
@app.get("/api/stats")
def api_stats(user: dict = Depends(auth_required)):
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
def api_contacts(user: dict = Depends(auth_required)):
    with get_db_conn() as conn:
        contacts = conn.execute("SELECT * FROM contacts").fetchall()
    return {"contacts": [dict(row) for row in contacts]}


@app.get("/api/logs")
def api_logs():
    with get_db_conn() as conn:
        logs = conn.execute("SELECT * FROM call_logs ORDER BY id DESC").fetchall()
    return {"logs": [dict(row) for row in logs]}


@app.get("/api-call-logs")
def api_call_logs(user: dict = Depends(auth_required)):
    with get_db_conn() as conn:
        logs = conn.execute("SELECT * FROM call_api_logs ORDER BY id DESC").fetchall()
    return {"logs": [dict(row) for row in logs]}