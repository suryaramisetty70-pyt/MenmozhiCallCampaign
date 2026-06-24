from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Optional
import sqlite3
import random
import string
from datetime import datetime, timedelta

from auth_utils import get_password_hash, verify_password, create_access_token, decode_token
from email_service import email_service
import os

router = APIRouter(prefix="/api")

# In-memory OTP store for registration
# { email: { "otp": "123456", "expires_at": datetime, "username": "user", "password": "hashed" } }
otp_store: Dict[str, dict] = {}

from database import get_connection

def get_db_conn():
    fallback_db = "postgresql://" + "menmozhi_database_user" + ":" + "ogvVlhpH9gpFP14n9Uj6A0azIUe1IdwN" + "@" + "dpg-d8u0hkjsq97s73ckv6c0-a" + "/menmozhi_database"
    DATABASE_URL = os.getenv("DATABASE_URL", fallback_db)
    return get_connection(DATABASE_URL)

class UserLogin(BaseModel):
    username: str
    password: str

class UserCreate(BaseModel):
    username: str
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    is_admin: bool = False
    user_id: int = None

class OTPSendRequest(BaseModel):
    email: str
    username: str
    password: str
    delivery_method: str = "email" # "email" or "sms"
    phone: str = None

class OTPVerifyRequest(BaseModel):
    email: str
    otp: str
    username: str
    password: str

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    email: str
    otp: str
    new_password: str

def generate_otp():
    return ''.join(random.choices(string.digits, k=6))

@router.post("/auth/send-otp")
def send_otp(request: OTPSendRequest):
    conn = get_db_conn()
    cursor = conn.cursor()
    
    # Check if email exists
    if cursor.execute("SELECT id FROM users WHERE email = ?", (request.email,)).fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="Email already registered")
        
    # Check if username exists
    if cursor.execute("SELECT id FROM users WHERE username = ?", (request.username,)).fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="Username already exists")
    conn.close()

    otp = generate_otp()
    hashed_password = get_password_hash(request.password)
    
    otp_store[request.email] = {
        "otp": otp,
        "expires_at": datetime.utcnow() + timedelta(minutes=10),
        "username": request.username,
        "password": hashed_password
    }
    
    if request.delivery_method == "sms" and request.phone:
        from sms_service import sms_service
        success = sms_service.send_otp(request.phone, otp)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to send SMS OTP")
    else:
        email_service.send_otp(request.email, otp)
        
    return {"message": f"OTP sent successfully via {request.delivery_method.upper()}", "email": request.email}

@router.post("/auth/verify-otp", response_model=Token)
def verify_otp_and_register(request: OTPVerifyRequest):
    otp_data = otp_store.get(request.email)
    if not otp_data:
        raise HTTPException(status_code=400, detail="No OTP requested for this email")
        
    if datetime.utcnow() > otp_data["expires_at"]:
        del otp_store[request.email]
        raise HTTPException(status_code=400, detail="OTP expired")
        
    if otp_data["otp"] != request.otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")
        
    conn = get_db_conn()
    cursor = conn.cursor()
    
    if cursor.execute("SELECT id FROM users WHERE username = ?", (request.username,)).fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="Username already exists")

    cursor.execute(
        "INSERT INTO users (username, email, password_hash, is_verified, created_at) VALUES (?, ?, ?, ?, ?)",
        (request.username, request.email, otp_data["password"], True, datetime.utcnow().isoformat())
    )
    user_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    del otp_store[request.email]
    
    token = create_access_token({"sub": str(user_id)})
    return Token(access_token=token, token_type="bearer", is_admin=False, user_id=user_id)

@router.post("/login", response_model=Token)
def login(user: UserLogin):
    conn = get_db_conn()
    cursor = conn.cursor()
    db_user = cursor.execute("SELECT * FROM users WHERE username = ?", (user.username,)).fetchone()
    conn.close()
    
    if not db_user or not verify_password(user.password, db_user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")
        
    token = create_access_token({"sub": str(db_user["id"])})
    return Token(access_token=token, token_type="bearer", is_admin=False, user_id=db_user["id"])

@router.post("/auth/forgot-password")
def forgot_password(request: ForgotPasswordRequest):
    conn = get_db_conn()
    cursor = conn.cursor()
    user = cursor.execute("SELECT id FROM users WHERE email = ?", (request.email,)).fetchone()
    conn.close()
    
    if not user:
        # Don't reveal if email exists or not
        return {"message": "If that email is registered, we have sent a reset OTP."}
        
    otp = generate_otp()
    otp_store[request.email + "_reset"] = {
        "otp": otp,
        "expires_at": datetime.utcnow() + timedelta(minutes=10),
        "user_id": user["id"]
    }
    
    email_service.send_otp(request.email, otp)
    return {"message": "If that email is registered, we have sent a reset OTP."}

@router.post("/auth/reset-password")
def reset_password(request: ResetPasswordRequest):
    store_key = request.email + "_reset"
    record = otp_store.get(store_key)
    
    if not record:
        raise HTTPException(status_code=400, detail="OTP expired or not requested")
        
    if record["otp"] != request.otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")
        
    if datetime.utcnow() > record["expires_at"]:
        del otp_store[store_key]
        raise HTTPException(status_code=400, detail="OTP has expired")
        
    conn = get_db_conn()
    cursor = conn.cursor()
    hashed_password = get_password_hash(request.new_password)
    cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hashed_password, record["user_id"]))
    conn.commit()
    conn.close()
    
    del otp_store[store_key]
    return {"message": "Password reset successfully. You can now login."}
