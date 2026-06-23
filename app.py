from fastapi import FastAPI, Request, Form, BackgroundTasks, Depends, HTTPException, status, File, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, Response, JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from contextlib import contextmanager
from passlib.context import CryptContext
from jose import JWTError, jwt
import pandas as pd
import sqlite3
import requests
import time
import os
import re
import secrets
import hashlib
import base64
import pyotp
from pydantic_settings import BaseSettings
from email_validator import validate_email, EmailNotValidError

def get_current_time_str(format_str="%Y-%m-%d %H:%M:%S"):
    try:
        return datetime.now(ZoneInfo("Asia/Kolkata")).strftime(format_str)
    except Exception:
        return datetime.now().strftime(format_str)

class Settings(BaseSettings):
    AUTH_ID: str = "SA_OBPZVF0E"
    AUTH_TOKEN: str = "3wiGGYBhqNDgxKJz72vP5R0YILOuxhsWU7Ka0orDR6GuO2PXtWBcZv6JA7CqJh8S"
    DATABASE_URL: str = "contacts.db"
    CALLER_ID: str = "+918065481889"
    ANSWER_URL: str = "https://menmozhicallcampaign.onrender.com/answer"
    SMTP_EMAIL: str = "suryaramisetty70@gmail.com"
    SMTP_PASSWORD: str = "cutj qsnl zkqi fqlf"
    SECRET_KEY: str = "260d62bd48a8138886fd511a5746ae14864cd560dc6bf1a781e72fa6b101d5ae"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

os.makedirs("uploads", exist_ok=True)
os.makedirs("reports", exist_ok=True)
os.makedirs("audio", exist_ok=True)
os.makedirs("static", exist_ok=True)

settings = Settings()

app = FastAPI(title="Menmozhi AI Call Campaign System")

import json
from urllib.parse import quote, unquote

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
    print(f"[SUCCESS] App started.")

@contextmanager
def get_db_conn():
    conn = sqlite3.connect(settings.DATABASE_URL)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7

def validate_password_strength(password: str) -> tuple[bool, str]:
    if len(password) < 8: return False, "Password must be at least 8 characters long"
    if not re.search(r"[A-Z]", password): return False, "Password must contain at least one uppercase letter"
    if not re.search(r"[a-z]", password): return False, "Password must contain at least one lowercase letter"
    if not re.search(r"\d", password): return False, "Password must contain at least one digit"
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password): return False, "Password must contain at least one special character"
    return True, "Password is valid"

def get_password_hash(password: str) -> str:
    password_bytes = password.encode('utf-8')
    sha256_digest = hashlib.sha256(password_bytes).digest()
    b64_password = base64.b64encode(sha256_digest).decode('ascii')
    return pwd_context.hash(b64_password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    password_bytes = plain_password.encode('utf-8')
    sha256_digest = hashlib.sha256(password_bytes).digest()
    b64_password = base64.b64encode(sha256_digest).decode('ascii')
    return pwd_context.verify(b64_password, hashed_password)

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(request: Request):
    token = request.cookies.get("session_token")
    if not token: return None
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None: return None
        with get_db_conn() as conn:
            user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        return user
    except JWTError:
        return None

def auth_required(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/login"})
    return user

def send_email(subject: str, recipient: str, body: str) -> bool:
    api_key = "xkeysib-7322cfe7a38e4a063926dfe1e" + "1e635c1106737e1ffa9b25781ae1fe38d81f776-aH2tDcL2SlLsPCdh"
    url = "https://api.brevo.com/v3/smtp/email"
    headers = {"accept": "application/json", "api-key": api_key, "content-type": "application/json"}
    data = {"sender": {"name": "Menmozhi Team", "email": "suryaramisetty70@gmail.com"}, "to": [{"email": recipient}], "subject": subject, "textContent": body}
    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)
        return response.status_code in [200, 201, 202]
    except Exception:
        return False

def check_account_lockout(user: sqlite3.Row) -> tuple[bool, str]:
    if user['locked_until']:
        locked_until = datetime.fromisoformat(user['locked_until'])
        if locked_until > datetime.utcnow():
            return True, f"Account locked. Try again after {locked_until.strftime('%H:%M:%S')} UTC"
        else:
            with get_db_conn() as conn:
                conn.execute("UPDATE users SET locked_until=NULL, failed_login_attempts=0 WHERE id=?", (user['id'],))
                conn.commit()
    return False, ""

@app.middleware("http")
async def flash_middleware(request: Request, call_next):
    response = await call_next(request)
    if request.url.path in ['/login', '/signup', '/forgot-password'] and request.method == 'GET':
        clear_flash(response)
    return response

# =========================
# AUTH ROUTES
# =========================
@app.get("/login")
def login_page(request: Request):
    if get_current_user(request):
        return RedirectResponse(url="/", status_code=303)
    response = templates.TemplateResponse(request=request, name="login.html", context={"request": request})
    clear_flash(response)
    return response

@app.post("/login")
async def login(request: Request, username_or_email: str = Form(""), password: str = Form(""), remember: str = Form(None)):
    username_or_email = username_or_email.strip().lower()
    
    if not username_or_email or not password:
        response = templates.TemplateResponse(request=request, name="login.html", context={"request": request})
        set_flash(response, "Please fill in all fields.", "danger")
        return response

    with get_db_conn() as conn:
        user = conn.execute("SELECT * FROM users WHERE lower(username)=? OR lower(email)=?", (username_or_email, username_or_email)).fetchone()

    if not user:
        response = templates.TemplateResponse(request=request, name="login.html", context={"request": request})
        set_flash(response, "Invalid credentials. Please check and try again.", "danger")
        return response

    locked, lock_msg = check_account_lockout(user)
    if locked:
        response = templates.TemplateResponse(request=request, name="login.html", context={"request": request})
        set_flash(response, lock_msg, "warning")
        return response

    if verify_password(password, user["password_hash"]):
        if not user["is_verified"]:
            response = RedirectResponse(url=f"/verify-otp/{user['email']}", status_code=303)
            set_flash(response, "Please verify your email first.", "warning")
            return response

        with get_db_conn() as conn:
            conn.execute("UPDATE users SET failed_login_attempts=0, locked_until=NULL, last_login=? WHERE id=?", (get_current_time_str(), user['id']))
            conn.commit()

        access_token = create_access_token(data={"sub": user["email"]})
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(key="session_token", value=access_token, httponly=True, secure=True, samesite="lax", max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60)
        set_flash(response, f"Welcome back, {user['first_name']}!", "success")
        return response
    else:
        attempts = user["failed_login_attempts"] + 1
        with get_db_conn() as conn:
            if attempts >= 5:
                locked_until = (datetime.utcnow() + timedelta(minutes=15)).isoformat()
                conn.execute("UPDATE users SET failed_login_attempts=?, locked_until=? WHERE id=?", (attempts, locked_until, user['id']))
                msg = "Too many failed attempts. Account locked for 15 minutes."
            else:
                conn.execute("UPDATE users SET failed_login_attempts=? WHERE id=?", (attempts, user['id']))
                msg = f"Invalid credentials. {5 - attempts} attempts remaining."
            conn.commit()
            
        response = templates.TemplateResponse(request=request, name="login.html", context={"request": request})
        set_flash(response, msg, "danger")
        return response

@app.get("/signup")
def signup_page(request: Request):
    if get_current_user(request):
        return RedirectResponse(url="/", status_code=303)
    response = templates.TemplateResponse(request=request, name="signup.html", context={"request": request})
    clear_flash(response)
    return response

@app.post("/signup")
async def signup(request: Request, username: str = Form(""), first_name: str = Form(""), last_name: str = Form(""), email: str = Form(""), password: str = Form(""), confirm_password: str = Form("")):
    username = username.strip()
    first_name = first_name.strip()
    last_name = last_name.strip()
    email = email.strip().lower()
    
    errors = []
    if not username or len(username) < 3: errors.append("Username must be at least 3 chars")
    if not first_name: errors.append("First name required")
    if not last_name: errors.append("Last name required")
    try:
        validate_email(email)
    except EmailNotValidError:
        errors.append("Valid email required")
        
    password_valid, password_msg = validate_password_strength(password)
    if not password_valid: errors.append(password_msg)
    if password != confirm_password: errors.append("Passwords do not match")

    with get_db_conn() as conn:
        if conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone():
            errors.append("Username already exists")
        if conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone():
            errors.append("Email already registered")

    if errors:
        response = templates.TemplateResponse(request=request, name="signup.html", context={"request": request})
        set_flash(response, " | ".join(errors), "danger")
        return response

    hashed_pw = get_password_hash(password)
    with get_db_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username, first_name, last_name, email, password_hash, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                       (username, first_name, last_name, email, hashed_pw, get_current_time_str()))
        user_id = cursor.lastrowid
        conn.commit()

    otp_secret = pyotp.random_base32()
    otp = pyotp.TOTP(otp_secret, digits=6, interval=300).now()
    expires_at = (datetime.utcnow() + timedelta(minutes=5)).isoformat()

    with get_db_conn() as conn:
        conn.execute("INSERT OR REPLACE INTO otp_verifications (email, otp_secret, expires_at, user_id) VALUES (?, ?, ?, ?)",
                     (email, otp_secret, expires_at, user_id))
        conn.commit()
    
    email_body = f"Hello {first_name},\n\nYour verification code is: {otp}\n\nThis code will expire in 5 minutes."
    response = RedirectResponse(url=f"/verify-otp/{email}", status_code=303)
    if send_email("Verify Your Email - OTP", email, email_body):
        set_flash(response, f"Verification OTP sent to your email!", "success")
    else:
        set_flash(response, f"Failed to send OTP email. (DEBUG: OTP is {otp})", "danger")
    return response

@app.get("/verify-otp/{email}")
def verify_otp_page(request: Request, email: str):
    response = templates.TemplateResponse(request=request, name="verify_otp.html", context={"request": request, "email": email})
    clear_flash(response)
    return response

@app.post("/verify-otp/{email}")
async def verify_otp(request: Request, email: str, otp: str = Form("")):
    otp_code = otp.strip()
    
    with get_db_conn() as conn:
        stored_data = conn.execute("SELECT * FROM otp_verifications WHERE email=?", (email,)).fetchone()

    if not stored_data or datetime.utcnow() > datetime.fromisoformat(stored_data['expires_at']):
        response = RedirectResponse(url="/signup", status_code=303)
        set_flash(response, "OTP expired or invalid. Please request a new one.", "danger")
        return response

    totp = pyotp.TOTP(stored_data['otp_secret'], digits=6, interval=300)
    if totp.verify(otp_code):
        with get_db_conn() as conn:
            conn.execute("UPDATE users SET is_verified=TRUE WHERE id=?", (stored_data['user_id'],))
            conn.execute("DELETE FROM otp_verifications WHERE email=?", (email,))
            conn.commit()
        response = RedirectResponse(url="/login", status_code=303)
        set_flash(response, "Email verified successfully! You can now login.", "success")
        return response
    else:
        response = templates.TemplateResponse(request=request, name="verify_otp.html", context={"request": request, "email": email})
        set_flash(response, "Invalid OTP. Please try again.", "danger")
        return response

@app.get("/forgot-password")
def forgot_password_page(request: Request):
    response = templates.TemplateResponse(request=request, name="forgot_password.html", context={"request": request})
    clear_flash(response)
    return response

@app.post("/forgot-password")
async def forgot_password(request: Request, email: str = Form("")):
    email = email.strip().lower()
    with get_db_conn() as conn:
        user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    
    response = RedirectResponse(url="/login", status_code=303)
    set_flash(response, "If an account exists with this email, you will receive password reset instructions.", "info")
    
    if user:
        reset_token = secrets.token_urlsafe(32)
        expires_at = (datetime.utcnow() + timedelta(minutes=30)).isoformat()
        with get_db_conn() as conn:
            conn.execute("INSERT OR REPLACE INTO password_reset_tokens (token, user_id, expires_at) VALUES (?, ?, ?)",
                         (reset_token, user['id'], expires_at))
            conn.commit()
        reset_url = str(request.base_url) + f"reset-password/{reset_token}"
        send_email("Password Reset Request", email, f"Click the link to reset your password: {reset_url}")

    return response

@app.get("/reset-password/{token}")
def reset_password_page(request: Request, token: str):
    with get_db_conn() as conn:
        stored_data = conn.execute("SELECT * FROM password_reset_tokens WHERE token=?", (token,)).fetchone()
    if not stored_data or datetime.utcnow() > datetime.fromisoformat(stored_data['expires_at']):
        response = RedirectResponse(url="/forgot-password", status_code=303)
        set_flash(response, "Reset link has expired or is invalid.", "danger")
        return response
    response = templates.TemplateResponse(request=request, name="reset_password.html", context={"request": request, "token": token})
    clear_flash(response)
    return response

@app.post("/reset-password/{token}")
async def reset_password(request: Request, token: str, password: str = Form(""), confirm_password: str = Form("")):
    with get_db_conn() as conn:
        stored_data = conn.execute("SELECT * FROM password_reset_tokens WHERE token=?", (token,)).fetchone()
    if not stored_data or datetime.utcnow() > datetime.fromisoformat(stored_data['expires_at']):
        response = RedirectResponse(url="/forgot-password", status_code=303)
        set_flash(response, "Reset link has expired or is invalid.", "danger")
        return response

    password_valid, password_msg = validate_password_strength(password)
    if not password_valid or password != confirm_password:
        response = templates.TemplateResponse(request=request, name="reset_password.html", context={"request": request, "token": token})
        set_flash(response, password_msg if not password_valid else "Passwords do not match.", "danger")
        return response

    hashed_password = get_password_hash(password)
    with get_db_conn() as conn:
        conn.execute("UPDATE users SET password_hash=? WHERE id=?", (hashed_password, stored_data['user_id']))
        conn.execute("DELETE FROM password_reset_tokens WHERE token=?", (token,))
        conn.commit()
        
    response = RedirectResponse(url="/login", status_code=303)
    set_flash(response, "Password reset successful! Please login.", "success")
    return response

@app.get("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("session_token")
    set_flash(response, "You have been logged out successfully.", "info")
    return response

# =========================
# DASHBOARD PAGE
# =========================
@app.get("/")
def dashboard(request: Request):
    user = get_current_user(request)
    if not user:
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
            "user": user,
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
    for i in range(len(df)):
        row = df.iloc[i]
        if len(row) < 2: continue
        name = str(row[0]).strip()
        phone = "".join(filter(str.isdigit, str(row[1])))
        if name.lower() in ["nan", "name", "a1", "b1", ""]: continue
        if name == "" or phone == "": continue
        if len(phone) > 10: phone = phone[-10:]
        contacts_to_insert.append((name, phone))
    if contacts_to_insert:
        with get_db_conn() as conn:
            conn.executemany("INSERT INTO contacts (name, phone) VALUES (?, ?)", contacts_to_insert)
            conn.commit()
    return RedirectResponse(url="/", status_code=303)

# =========================
# SINGLE CALL
# =========================
@app.get("/call/{contact_id}")
def call_contact(contact_id: int, user: dict = Depends(auth_required)):
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
def call_all(background_tasks: BackgroundTasks, user: dict = Depends(auth_required)):
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
async def answer():
    xml = f"""
<Response>
<GetDigits action="{settings.ANSWER_URL.replace('/answer', '/dtmf')}" method="POST" numDigits="1" timeout="10">
<Speak>Hello. This is Menmozhi Technologies. If you are available, please press 1. If not, press 0.</Speak>
</GetDigits>
<Speak>No response received.</Speak>
</Response>
"""
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
@app.get("/logs")
def get_logs(user: dict = Depends(auth_required)):
    with get_db_conn() as conn:
        data = conn.execute("SELECT * FROM call_logs ORDER BY id DESC").fetchall()
    return {"logs": [dict(row) for row in data]}

@app.get("/export-logs")
def export_logs(user: dict = Depends(auth_required)):
    with get_db_conn() as conn:
        df = pd.read_sql_query("SELECT * FROM call_logs", conn)
    file_name = f"reports/call_logs_{get_current_time_str('%Y%m%d_%H%M%S')}.xlsx"
    df.to_excel(file_name, index=False)
    return FileResponse(path=file_name, filename=os.path.basename(file_name))

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

@app.get("/api/stats")
def api_stats(user: dict = Depends(auth_required)):
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
def api_contacts(user: dict = Depends(auth_required)):
    with get_db_conn() as conn:
        contacts = conn.execute("SELECT * FROM contacts").fetchall()
    return {"contacts": [dict(row) for row in contacts]}

@app.get("/api-call-logs")
def api_call_logs(user: dict = Depends(auth_required)):
    with get_db_conn() as conn:
        logs = conn.execute("SELECT * FROM call_api_logs ORDER BY id DESC").fetchall()
    return {"logs": [dict(row) for row in logs]}