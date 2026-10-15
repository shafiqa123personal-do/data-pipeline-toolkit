"""Email a finished report through Gmail (needs an App Password). Optional:
when the Gmail settings are not in .env, emailing is skipped."""
import logging
import smtplib
from email.message import EmailMessage
from pathlib import Path

import config

log = logging.getLogger(__name__)


def send_report(path, subject, smtp_class=smtplib.SMTP_SSL):
    if not (config.GMAIL_ADDRESS and config.GMAIL_APP_PASSWORD):
        log.info("Email skipped - GMAIL_ADDRESS / GMAIL_APP_PASSWORD are not set in .env")
        return False

    path = Path(path)
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = config.GMAIL_ADDRESS
    message["To"] = config.REPORT_TO or config.GMAIL_ADDRESS
    message.set_content(f"Your report is attached: {path.name}\n\n"
                        "Sent automatically by Data Pipeline Toolkit.")
    message.add_attachment(path.read_bytes(), maintype="application",
                           subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           filename=path.name)
    try:
        with smtp_class("smtp.gmail.com", 465, timeout=30) as smtp:
            smtp.login(config.GMAIL_ADDRESS, config.GMAIL_APP_PASSWORD)
            smtp.send_message(message)
    except (smtplib.SMTPException, OSError) as error:
        log.error("Email failed: %s", error)
        return False
    log.info("Report emailed to %s", message["To"])
    return True
