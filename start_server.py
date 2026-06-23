import uvicorn
from pyngrok import ngrok
import time
import re
import sys

def main():
    try:
        public_url = ngrok.connect(8005).public_url
        print(f"Ngrok Tunnel URL: {public_url}")
        
        with open("app.py", "r") as f:
            content = f.read()
            
        content = re.sub(
            r'ANSWER_URL: str = ".*?"', 
            f'ANSWER_URL: str = "{public_url}/answer"', 
            content
        )
        
        with open("app.py", "w") as f:
            f.write(content)
            
        print("Updated app.py with ngrok URL.")
        print("Starting uvicorn...")
        
        import subprocess
        subprocess.run([sys.executable, "-m", "uvicorn", "app:app", "--port", "8005"])
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
