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

def get_db_conn():
    # Use the same connection approach as app.py
    DATABASE_URL = os.getenv("DATABASE_URL", "contacts.db")
    conn = sqlite3.connect(DATABASE_URL)
    conn.row_factory = sqlite3.Row
    return conn

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

class OTPVerifyRequest(BaseModel):
    email: str
    otp: str
    username: str
    password: str

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
    
    email_service.send_otp(request.email, otp)
    return {"message": "OTP sent to your email", "email": request.email}

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
