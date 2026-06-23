import os
from datetime import datetime, timedelta
from typing import Optional, Dict
import jwt
from passlib.context import CryptContext

# ═══════════════════════════════════════════════════════════
# PASSWORD HASHING CONFIG
# ═══════════════════════════════════════════════════════════
# Uses bcrypt algorithm for secure password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ═══════════════════════════════════════════════════════════
# JWT CONFIGURATION
# ═══════════════════════════════════════════════════════════
SECRET_KEY = os.getenv("SECRET_KEY", "callcampaign-secret-key-change-in-production-2024")
ALGORITHM = "HS256"  # JWT signing algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_token(token: str) -> Dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

def get_current_user_id(token: str) -> Optional[int]:
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        if user_id is None:
            return None
        return int(user_id)
    except Exception:
        return None
