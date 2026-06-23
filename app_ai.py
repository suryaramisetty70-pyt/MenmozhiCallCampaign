from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
import requests
import os
import sqlite3

ai_router = APIRouter(prefix="/api/ai")

class ChatRequest(BaseModel):
    message: str

class ScriptRequest(BaseModel):
    prompt: str

def get_db_conn():
    DATABASE_URL = os.getenv("DATABASE_URL", "contacts.db")
    conn = sqlite3.connect(DATABASE_URL)
    conn.row_factory = sqlite3.Row
    return conn

def call_groq_api(messages: list) -> str:
    groq_api_key = os.getenv("GROQ_API_KEY")
    if not groq_api_key:
        raise HTTPException(status_code=500, detail="Groq API key not configured")
    
    headers = {
        "Authorization": f"Bearer {groq_api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "llama3-8b-8192",
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 1024
    }
    
    try:
        response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=15)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI Service Error: {str(e)}")

@ai_router.post("/chat")
def ai_chat(req: ChatRequest):
    # Fetch some stats to give the AI context
    with get_db_conn() as conn:
        total_calls = conn.execute("SELECT COUNT(*) FROM call_logs").fetchone()[0]
        available = conn.execute("SELECT COUNT(*) FROM call_logs WHERE status='AVAILABLE'").fetchone()[0]
        not_available = conn.execute("SELECT COUNT(*) FROM call_logs WHERE status='NOT AVAILABLE'").fetchone()[0]
        no_response = conn.execute("SELECT COUNT(*) FROM call_logs WHERE status='NO RESPONSE'").fetchone()[0]
        total_contacts = conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]

    system_prompt = f"""You are the Call Campaign AI Assistant. 
You analyze call campaign data and answer user questions concisely and professionally.
Current Campaign Stats:
- Total Contacts in DB: {total_contacts}
- Total Calls Logged: {total_calls}
- Contacts Available (Success): {available}
- Contacts Not Available: {not_available}
- Contacts No Response: {no_response}

Answer the user's question based on these stats. Keep responses under 3 sentences unless asked for details. Never use markdown formatting in your response (just plain text)."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": req.message}
    ]
    
    reply = call_groq_api(messages)
    return {"reply": reply}

@ai_router.post("/generate-script")
def generate_script(req: ScriptRequest):
    system_prompt = """You are an expert telemarketing script writer. 
Write a short, engaging, professional voice script (under 30 seconds to read) for a robotic or AI voice caller.
Do NOT include any stage directions like [Pause] or (Cheerful voice). Just return the exact text to be spoken.
The script MUST end with a clear instruction: 'If you are interested, please press 1. If not, press 0.'"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": req.prompt}
    ]
    
    script = call_groq_api(messages)
    return {"script": script}
