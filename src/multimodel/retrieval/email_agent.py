import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os


SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = "thorvikash@gmail.com"
SMTP_PASSWORD = "hwyj crbi kcol nbpl"

def send_email_notification(
    to_email: str,
    subject: str,
    body: str
):
    msg = MIMEMultipart()
    msg["From"] = SMTP_USER
    msg["To"] = to_email
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)
