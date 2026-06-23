import smtplib
import os
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import logging
from dotenv import load_dotenv

env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_EMAIL", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.from_email = os.getenv("SMTP_FROM", self.smtp_user)
        self.use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
        self.enabled = bool(self.smtp_user and self.smtp_password)
    
    def send_email(self, to_email: str, subject: str, body: str, html_body: Optional[str] = None) -> bool:
        if not self.enabled:
            logger.warning(f"Email service not configured. Would send to {to_email}: {subject}")
            print(f"OTP for {to_email}:\n{body}")
            return False
        
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.from_email
            msg['To'] = to_email
            msg.attach(MIMEText(body, 'plain'))
            
            if html_body:
                msg.attach(MIMEText(html_body, 'html'))
            
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.sendmail(self.from_email, to_email, msg.as_string())
            
            logger.info(f"Email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            print(f"FAILED TO SEND EMAIL: {e}")
            return False
    
    def send_otp(self, to_email: str, otp: str) -> bool:
        subject = "Your CallCampaign Verification Code"
        body = f"Your verification code is: {otp}\n\nThis code will expire in 10 minutes.\n\n- CallCampaign Team"
        
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; background-color: #f4f4f4; margin: 0; padding: 20px; }}
        .container {{ background-color: white; border-radius: 10px; padding: 30px; max-width: 500px; margin: 0 auto; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .code {{ font-size: 32px; font-weight: bold; color: #4F46E5; text-align: center; letter-spacing: 5px; padding: 20px; background: #f0f0f0; border-radius: 5px; margin: 20px 0; }}
        .footer {{ color: #666; font-size: 12px; margin-top: 20px; text-align: center; }}
    </style>
</head>
<body>
    <div class="container">
        <h2 style="color: #333;">Verification Code</h2>
        <p>Your verification code is:</p>
        <div class="code">{otp}</div>
        <p>This code will expire in <strong>10 minutes</strong>.</p>
        <div class="footer">
            <p>Menmozhi Call Campaign System</p>
        </div>
    </div>
</body>
</html>
        """
        return self.send_email(to_email, subject, body, html_body)

email_service = EmailService()
