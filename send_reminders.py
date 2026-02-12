import os
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage

from app import app
from db import db
from models import AdminUser, Equipment, Service


def send_email(to_address, subject, body):
    host = os.environ.get("SMTP_HOST")
    port = int(os.environ.get("SMTP_PORT", "587"))
    username = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD")
    sender = os.environ.get("SMTP_FROM") or username
    use_tls = os.environ.get("SMTP_TLS", "true").lower() == "true"

    if not host or not sender:
        raise RuntimeError("SMTP_HOST and SMTP_FROM (or SMTP_USER) must be set.")

    message = EmailMessage()
    message["From"] = sender
    message["To"] = to_address
    message["Subject"] = subject
    message.set_content(body)

    with smtplib.SMTP(host, port) as server:
        if use_tls:
            server.starttls()
        if username and password:
            server.login(username, password)
        server.send_message(message)


def build_reminders():
    days = int(os.environ.get("REMINDER_DAYS", "7"))
    cutoff = datetime.utcnow().date() + timedelta(days=days)
    reminders = {}

    equipment_list = Equipment.query.all()
    for equipment in equipment_list:
        latest_service = (
            Service.query.filter_by(equipment_id=equipment.id)
            .order_by(Service.date.desc())
            .first()
        )
        if not latest_service or not latest_service.next_service:
            continue
        if latest_service.next_service > cutoff:
            continue
        reminders.setdefault(equipment.admin_user_id, []).append(
            {
                "code": equipment.code,
                "type": equipment.type,
                "next_service": latest_service.next_service,
                "mileage": equipment.mileage,
            }
        )

    return reminders


def main():
    with app.app_context():
        reminders = build_reminders()
        if not reminders:
            print("No upcoming services within the reminder window.")
            return

        for user_id, items in reminders.items():
            user = AdminUser.query.filter_by(id=user_id).first()
            if not user:
                continue
            lines = [
                "Upcoming service reminders:",
                "",
            ]
            for item in items:
                mileage = item["mileage"] if item["mileage"] is not None else "N/A"
                lines.append(f"- {item['code']} ({item['type']}) | Next service: {item['next_service']} | Mileage: {mileage}")
            body = "\n".join(lines)
            send_email(user.email, "ConComply service reminders", body)
            print(f"Sent reminder to {user.email}")


if __name__ == "__main__":
    main()
