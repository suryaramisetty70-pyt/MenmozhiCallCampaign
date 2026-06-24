import requests
import os
import json

class SMSService:
    def __init__(self):
        # Using environment variables so it works locally and on Render.
        # Fallback to a test key if not provided (Fast2SMS API Key)
        self.api_key = os.getenv("FAST2SMS_API_KEY", "")
        self.api_url = "https://www.fast2sms.com/dev/bulkV2"

    def send_otp(self, phone: str, otp: str):
        if not self.api_key:
            print(f"[WARN] FAST2SMS_API_KEY not set! Simulating SMS to {phone}: OTP is {otp}")
            return True

        # Fast2SMS requires 10-digit number. Remove +91 if present.
        phone_clean = phone.replace("+91", "").replace(" ", "").strip()
        if len(phone_clean) > 10:
            phone_clean = phone_clean[-10:]

        payload = {
            "route": "otp",
            "variables_values": otp,
            "numbers": phone_clean,
        }

        headers = {
            "authorization": self.api_key,
            "Content-Type": "application/x-www-form-urlencoded"
        }

        try:
            response = requests.post(self.api_url, data=payload, headers=headers)
            res_data = response.json()
            if res_data.get("return") == True:
                print(f"[INFO] SMS OTP sent successfully to {phone_clean}")
                return True
            else:
                print(f"[ERROR] Failed to send SMS OTP: {res_data}")
                return False
        except Exception as e:
            print(f"[ERROR] Exception while sending SMS: {e}")
            return False

sms_service = SMSService()
