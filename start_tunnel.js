const localtunnel = require('localtunnel');
const { spawn } = require('child_process');
const fs = require('fs');

(async () => {
  const tunnel = await localtunnel({ port: 8005 });
  console.log('Tunnel URL:', tunnel.url);

  // Update app.py
  let appCode = fs.readFileSync('app.py', 'utf8');
  appCode = appCode.replace(/ANSWER_URL:\s*str\s*=\s*".*?"/, `ANSWER_URL: str = "${tunnel.url}/answer"`);
  fs.writeFileSync('app.py', appCode);
  console.log('Updated app.py with the tunnel URL');

  // Start uvicorn
  const uvicorn = spawn('python', ['-m', 'uvicorn', 'app:app', '--port', '8005'], { stdio: 'inherit' });

  tunnel.on('close', () => {
    console.log('Tunnel closed');
    uvicorn.kill();
  });
})();
