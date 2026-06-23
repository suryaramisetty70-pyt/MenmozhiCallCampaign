import subprocess
import re
import sys
import os

def main():
    print("Starting serveo tunnel...")
    process = subprocess.Popen(
        ["ssh", "-o", "StrictHostKeyChecking=no", "-R", "80:localhost:8005", "serveo.net"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    
    tunnel_url = None
    for line in iter(process.stdout.readline, ''):
        print(line, end='')
        match = re.search(r'https://[a-zA-Z0-9-]+\.serveo\.net', line)
        if match:
            tunnel_url = match.group(0)
            break
            
    if not tunnel_url:
        print("Failed to get serveo url.")
        sys.exit(1)
        
    print(f"Tunnel URL found: {tunnel_url}")
    
    with open("app.py", "r") as f:
        content = f.read()
        
    content = re.sub(
        r'ANSWER_URL: str = ".*?"', 
        f'ANSWER_URL: str = "{tunnel_url}/answer"', 
        content
    )
    
    # Fix the XML newline issue for the voice
    content = content.replace('    xml = f"""\n<Response>', '    xml = f"""<Response>')
    
    with open("app.py", "w") as f:
        f.write(content)
        
    print("Updated app.py with tunnel URL and fixed XML.")
    
    print("Starting uvicorn...")
    uvicorn_process = subprocess.Popen([sys.executable, "-m", "uvicorn", "app:app", "--port", "8005"])
    
    try:
        uvicorn_process.wait()
    except KeyboardInterrupt:
        uvicorn_process.terminate()
        process.terminate()

if __name__ == "__main__":
    main()
