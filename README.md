# ConComply Maintenance

ConComply is a lightweight Flask app for tracking equipment service and repair history. It lets a crew register assets, log maintenance events, and export compliance-ready CSV reports per machine.

## Features
- Admin login with hashed passwords
- Admin/tech roles with team management
- Equipment inventory with search and filters
- Service and repair logs per asset
- Cost items with totals for services and repairs
- Upload receipts and attachments per service or repair
- QR check-ins for mileage and issue reporting
- One-click CSV export for audits
- Email reminders for upcoming services

## Getting started
1) Create a virtual environment and install dependencies:
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

2) Create a `.env` file in the project root:
```bash
SECRET_KEY=replace-with-a-long-random-string
```

3) Initialize the SQLite database:
```bash
python create_db.py
```

If you already have data and need the new tables/columns:
```bash
python migrate_features.py
```

4) Run the app:
```bash
flask --app app run
```

Visit `http://127.0.0.1:5000` in your browser.

## How it works
- Register an admin account.
- Add equipment with VIN, make, model, and service requirements.
- Log service and repair entries, including mileage and costs.
- Attach receipts or photos to service and repair entries.
- Scan a QR code to submit mileage and issue check-ins.
- Export per-equipment CSV reports for compliance.
- Send email reminders for upcoming services.

## Email reminders
Set SMTP environment variables and run:
```bash
python send_reminders.py
```

Required variables:
- `SMTP_HOST`
- `SMTP_FROM` (or `SMTP_USER`)

Optional variables:
- `SMTP_PORT` (default 587)
- `SMTP_USER`
- `SMTP_PASSWORD`
- `SMTP_TLS` (default true)
- `REMINDER_DAYS` (default 7)

## Security notes
- Passwords are hashed using Werkzeug before storage.
- CSRF protection is enforced for all POST requests.
- CSV export sanitizes fields to prevent spreadsheet formula injection.
- Attachments are stored on disk in `instance/uploads` and are protected by login checks.
- Audit logs are stored for key actions.
- Secrets are loaded from `.env` and `.env` is ignored by Git.

## Project structure
- `app.py` Flask routes and CSV export
- `models.py` SQLAlchemy models
- `db.py` database setup
- `migrate_features.py` schema updates for new features
- `send_reminders.py` email reminder script
- `templates/` HTML templates
- `static/` CSS and JS assets
