"""Notification service: Email (SMTP) + SMS (Twilio)."""

import logging
import os
import smtplib
from email.mime.text import MIMEText

from twilio.rest import Client as TwilioClient

logger = logging.getLogger(__name__)


class NotificationService:
    """Sends alerts via email and SMS."""

    def __init__(self):
        self._email_user = os.environ.get("SMTP_EMAIL")
        self._email_pass = os.environ.get("SMTP_PASSWORD")
        self._smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
        self._smtp_port = int(os.environ.get("SMTP_PORT", "587"))
        self._notify_email = os.environ.get("NOTIFY_EMAIL")

        self._twilio_sid = os.environ.get("TWILIO_SID")
        self._twilio_token = os.environ.get("TWILIO_AUTH_TOKEN")
        self._twilio_from = os.environ.get("TWILIO_FROM_NUMBER")
        self._notify_phone = os.environ.get("NOTIFY_PHONE")

    def send_email(self, subject: str, body: str) -> bool:
        if not all([self._email_user, self._email_pass, self._notify_email]):
            logger.warning("Email not configured. Skipping.")
            return False
        try:
            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["From"] = self._email_user
            msg["To"] = self._notify_email
            with smtplib.SMTP(self._smtp_host, self._smtp_port) as server:
                server.starttls()
                server.login(self._email_user, self._email_pass)
                server.send_message(msg)
            logger.info("Email sent: %s", subject)
            return True
        except Exception as e:
            logger.error("Email failed: %s", e)
            return False

    def send_sms(self, body: str) -> bool:
        if not all([self._twilio_sid, self._twilio_token, self._twilio_from, self._notify_phone]):
            logger.warning("SMS not configured. Skipping.")
            return False
        try:
            client = TwilioClient(self._twilio_sid, self._twilio_token)
            client.messages.create(
                body=body, from_=self._twilio_from, to=self._notify_phone
            )
            logger.info("SMS sent to %s", self._notify_phone)
            return True
        except Exception as e:
            logger.error("SMS failed: %s", e)
            return False

    def alert(self, subject: str, body: str) -> None:
        """Send alert via both email and SMS."""
        self.send_email(subject, body)
        self.send_sms(f"{subject}\n{body[:140]}")
