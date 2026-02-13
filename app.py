from datetime import datetime
import csv
import io
import os
import secrets
from functools import wraps

import qrcode
from dotenv import load_dotenv
from flask import Flask, render_template, request, flash, redirect, url_for, session, Response, send_from_directory
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from werkzeug.utils import secure_filename

from db import db, basedir
from models import (
    AdminUser,
    Equipment,
    Service,
    Repair,
    ServiceAttachment,
    RepairAttachment,
    ServiceCostItem,
    RepairCostItem,
    EquipmentCheckIn,
    AuditLog,
    BidTrackerEntry,
)
from utils import hash_password, verify_password

app = Flask(__name__)
load_dotenv()
secret_key = os.environ.get("SECRET_KEY")
if not secret_key:
    raise RuntimeError("SECRET_KEY is required to run the app securely.")
app.secret_key = secret_key
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(basedir, "db.db")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
app.config["UPLOAD_FOLDER"] = os.path.join(basedir, "instance", "uploads")
db.init_app(app)

ALLOWED_EXTENSIONS = {
    "pdf", "png", "jpg", "jpeg", "gif",
    "doc", "docx", "xls", "xlsx", "txt"
}

IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

def generate_csrf_token():
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token

@app.context_processor
def inject_csrf_token():
    return {"csrf_token": generate_csrf_token()}

@app.context_processor
def inject_current_user():
    user_id = session.get("user_id")
    user = AdminUser.query.filter_by(id=user_id).first() if user_id else None
    return {"current_user": user}

@app.before_request
def csrf_protect():
    if request.method == "POST":
        session_token = session.get("_csrf_token")
        form_token = request.form.get("csrf_token")
        if not session_token or not form_token or session_token != form_token:
            flash("Invalid CSRF token. Please try again.", "error")
            return redirect(request.referrer or url_for("login"))

def sanitize_csv_value(value):
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return value
    text = str(value)
    if text and text[0] in ("=", "+", "-", "@"):
        return "'" + text
    return text

def allowed_file(filename):
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS

def store_attachments(files, owner_id, attachment_model):
    attachments = []
    for upload in files:
        if not upload or not upload.filename:
            continue
        if not allowed_file(upload.filename):
            raise ValueError("Invalid attachment type.")
        safe_name = secure_filename(upload.filename)
        ext = safe_name.rsplit(".", 1)[1].lower() if "." in safe_name else "dat"
        stored_name = f"{secrets.token_hex(16)}.{ext}"
        upload_path = os.path.join(app.config["UPLOAD_FOLDER"], stored_name)
        upload.save(upload_path)
        attachments.append(
            attachment_model(
                **owner_id,
                original_name=safe_name,
                stored_name=stored_name,
            )
        )
    return attachments

def is_image_filename(filename):
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in IMAGE_EXTENSIONS

def parse_cost_items(descriptions, amounts):
    items = []
    total = 0.0
    for desc, amount in zip(descriptions, amounts):
        desc = (desc or "").strip()
        amount = (amount or "").strip()
        if not desc and not amount:
            continue
        if not desc:
            raise ValueError("Each cost item needs a description.")
        if not amount:
            raise ValueError("Each cost item needs an amount.")
        try:
            value = float(amount)
        except ValueError as exc:
            raise ValueError("Cost item amounts must be numbers.") from exc
        items.append((desc, value))
        total += value
    return items, total

def parse_optional_int(value, field_name, row_index):
    if value is None or value == "":
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"Row {row_index}: {field_name} must be a whole number.") from exc

def parse_optional_float(value, field_name, row_index):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"Row {row_index}: {field_name} must be a number.") from exc

def validate_choice(value, allowed_values, field_name, row_index=None):
    if value is None or value == "":
        return None
    if value not in allowed_values:
        prefix = f"Row {row_index}: " if row_index else ""
        allowed_text = ", ".join(allowed_values)
        raise ValueError(f"{prefix}{field_name} must be one of: {allowed_text}.")
    return value

def log_action(user, action, entity, entity_id=None, details=None):
    entry = AuditLog(
        user_id=user.id if user else None,
        action=action,
        entity=entity,
        entity_id=entity_id,
        details=details,
    )
    db.session.add(entry)

def login_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        user = AdminUser.query.filter_by(id=session.get("user_id")).first()
        if not user:
            flash("Please log in!", "error")
            return redirect(url_for("login"))
        return view_func(user, *args, **kwargs)
    return wrapper

def admin_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        user = AdminUser.query.filter_by(id=session.get("user_id")).first()
        if not user:
            flash("Please log in!", "error")
            return redirect(url_for("login"))
        if user.role != "admin":
            flash("Admin access required.", "error")
            return redirect(url_for("dashboard"))
        return view_func(user, *args, **kwargs)
    return wrapper

@app.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard(user):
    if request.method == "GET":
        equipment_count = Equipment.query.filter_by(admin_user_id=user.id).count()
        service_count = Service.query.join(Equipment, Service.equipment_id == Equipment.id).filter(Equipment.admin_user_id == user.id).count()
        repair_count = Repair.query.join(Equipment, Repair.equipment_id == Equipment.id).filter(Equipment.admin_user_id == user.id).count()
        return render_template(
            "dashboard.html",
            user=user,
            equipment_count=equipment_count,
            service_count=service_count,
            repair_count=repair_count,
        )
    return redirect(url_for("dashboard"))
    
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")
    else:
        email = request.form.get("email")
        password = request.form.get("password")

        user = AdminUser.query.filter_by(email=email).first()
        if not user:
            flash("User not found!", "error")
            return redirect(url_for("login"))

        if user and verify_password(password, user.password_hash):
            session["user_id"] = user.id
            log_action(user, "login", "admin_user", user.id)
            db.session.commit()
            return redirect("/dashboard")
        else:
            flash("Wrong password!", "error")
            return redirect(url_for("login"))
        
@app.route("/logout")
def logout():
    session.pop("user_id", None)
    flash("Logged out successfully!", "success")
    return redirect(url_for("login"))

@app.route("/registration", methods=["GET", "POST"])
def registration():
    if request.method == "GET":
        return render_template("registration.html")
    else:
        email = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        if password != confirm_password:
            flash("Password do not match!", "error")
            return redirect(url_for("registration"))
        if not email or not password:
            flash("Email and password are required.", "error")
            return redirect(url_for("registration"))
        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return redirect(url_for("registration"))
        existing_user = AdminUser.query.filter_by(email=email).first()
        if existing_user:
            flash("Account already exists. Please log in.", "error")
            return redirect(url_for("login"))
        else:
            new_user = AdminUser(email=email, password_hash=hash_password(password), role="admin")
            db.session.add(new_user)
            db.session.flush()
            log_action(new_user, "create", "admin_user", new_user.id, "self-registration")
            db.session.commit()
    
    return redirect(url_for("login"))

@app.route("/team", methods=["GET", "POST"])
@admin_required
def team(user):
    if request.method == "GET":
        team_members = AdminUser.query.order_by(AdminUser.registration_date.desc()).all()
        return render_template("team.html", user=user, team_members=team_members)

    email = request.form.get("email")
    password = request.form.get("password")
    role = request.form.get("role", "tech")

    if not email or not password:
        flash("Email and password are required.", "error")
        return redirect(url_for("team"))
    if role not in ("admin", "tech"):
        flash("Invalid role.", "error")
        return redirect(url_for("team"))
    if len(password) < 8:
        flash("Password must be at least 8 characters.", "error")
        return redirect(url_for("team"))

    existing_user = AdminUser.query.filter_by(email=email).first()
    if existing_user:
        flash("User already exists.", "error")
        return redirect(url_for("team"))

    new_user = AdminUser(email=email, password_hash=hash_password(password), role=role)
    db.session.add(new_user)
    db.session.flush()
    log_action(user, "create", "admin_user", new_user.id, f"role={role}")
    db.session.commit()
    flash("Team member created.", "success")
    return redirect(url_for("team"))

@app.route("/bid-tracker", methods=["GET", "POST"])
@login_required
def bid_tracker(user):
    allowed_roles = ("GC", "SUB", "PQ")
    allowed_types = ("Municipal", "ICI/Private", "Subdivision", "MTO")
    allowed_statuses = ("Submitted", "No Bid")

    if request.method == "GET":
        entries = (
            BidTrackerEntry.query
            .filter_by(admin_user_id=user.id)
            .order_by(BidTrackerEntry.created_at.desc())
            .all()
        )
        return render_template("bid_tracker.html", entries=entries)

    fields = {
        "line_number": request.form.getlist("line_number"),
        "owner": request.form.getlist("owner"),
        "project_number": request.form.getlist("project_number"),
        "project_name": request.form.getlist("project_name"),
        "location": request.form.getlist("location"),
        "city": request.form.getlist("city"),
        "closing_date": request.form.getlist("closing_date"),
        "closing_time": request.form.getlist("closing_time"),
        "role": request.form.getlist("role"),
        "asphalt_tonnage": request.form.getlist("asphalt_tonnage"),
        "bid_type": request.form.getlist("bid_type"),
        "estimator_responsible": request.form.getlist("estimator_responsible"),
        "submission_status": request.form.getlist("submission_status"),
        "notes_comments": request.form.getlist("notes_comments"),
        "follow_up_notes": request.form.getlist("follow_up_notes"),
        "gc_awarded": request.form.getlist("gc_awarded"),
        "amount_award": request.form.getlist("amount_award"),
    }
    row_count = max((len(values) for values in fields.values()), default=0)
    created = 0

    try:
        for index in range(row_count):
            row_values = {key: (values[index] if index < len(values) else "") for key, values in fields.items()}
            if not any(value.strip() for value in row_values.values() if isinstance(value, str)):
                continue

            row_index = index + 1
            closing_date = (
                datetime.strptime(row_values["closing_date"], "%Y-%m-%d").date()
                if row_values["closing_date"]
                else None
            )
            closing_time = (
                datetime.strptime(row_values["closing_time"], "%H:%M").time()
                if row_values["closing_time"]
                else None
            )
            entry = BidTrackerEntry(
                admin_user_id=user.id,
                line_number=parse_optional_int(row_values["line_number"], "No.", row_index),
                owner=row_values["owner"].strip() or None,
                project_number=row_values["project_number"].strip() or None,
                project_name=row_values["project_name"].strip() or None,
                location=row_values["location"].strip() or None,
                city=row_values["city"].strip() or None,
                closing_date=closing_date,
                closing_time=closing_time,
                role=validate_choice(row_values["role"].strip(), allowed_roles, "Role", row_index),
                asphalt_tonnage=parse_optional_float(row_values["asphalt_tonnage"], "Asphalt Tonnage", row_index),
                bid_type=validate_choice(row_values["bid_type"].strip(), allowed_types, "Type", row_index),
                estimator_responsible=row_values["estimator_responsible"].strip() or None,
                submission_status=validate_choice(row_values["submission_status"].strip(), allowed_statuses, "Bid Status", row_index),
                notes_comments=row_values["notes_comments"].strip() or None,
                follow_up_notes=row_values["follow_up_notes"].strip() or None,
                gc_awarded=row_values["gc_awarded"].strip() or None,
                amount_award=parse_optional_float(row_values["amount_award"], "Amount of Award", row_index),
            )
            db.session.add(entry)
            created += 1

        if created == 0:
            flash("No rows were added. Fill out at least one field.", "error")
            return redirect(url_for("bid_tracker"))

        log_action(user, "create", "bid_tracker_entry", details=f"rows={created}")
        db.session.commit()
        flash(f"{created} row(s) added to the bid tracker.", "success")
        return redirect(url_for("bid_tracker"))
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "error")
        return redirect(url_for("bid_tracker"))
    except Exception:
        db.session.rollback()
        app.logger.exception("Error saving bid tracker entries")
        flash("Error saving bid tracker entries. Please try again.", "error")
        return redirect(url_for("bid_tracker"))

@app.route("/bid-tracker/<int:entry_id>/update", methods=["POST"])
@login_required
def update_bid_tracker_entry(user, entry_id):
    allowed_roles = ("GC", "SUB", "PQ")
    allowed_types = ("Municipal", "ICI/Private", "Subdivision", "MTO")
    allowed_statuses = ("Submitted", "No Bid")

    entry = BidTrackerEntry.query.filter_by(id=entry_id, admin_user_id=user.id).first()
    if not entry:
        flash("Bid tracker entry not found.", "error")
        return redirect(url_for("bid_tracker"))

    try:
        closing_date_raw = request.form.get("closing_date")
        closing_time_raw = request.form.get("closing_time")
        entry.line_number = parse_optional_int(request.form.get("line_number"), "No.", 1)
        entry.owner = (request.form.get("owner") or "").strip() or None
        entry.project_number = (request.form.get("project_number") or "").strip() or None
        entry.project_name = (request.form.get("project_name") or "").strip() or None
        entry.location = (request.form.get("location") or "").strip() or None
        entry.city = (request.form.get("city") or "").strip() or None
        entry.closing_date = (
            datetime.strptime(closing_date_raw, "%Y-%m-%d").date()
            if closing_date_raw
            else None
        )
        entry.closing_time = (
            datetime.strptime(closing_time_raw, "%H:%M").time()
            if closing_time_raw
            else None
        )
        entry.role = validate_choice((request.form.get("role") or "").strip(), allowed_roles, "Role")
        entry.asphalt_tonnage = parse_optional_float(request.form.get("asphalt_tonnage"), "Asphalt Tonnage", 1)
        entry.bid_type = validate_choice((request.form.get("bid_type") or "").strip(), allowed_types, "Type")
        entry.estimator_responsible = (request.form.get("estimator_responsible") or "").strip() or None
        entry.submission_status = validate_choice((request.form.get("submission_status") or "").strip(), allowed_statuses, "Bid Status")
        entry.notes_comments = (request.form.get("notes_comments") or "").strip() or None
        entry.follow_up_notes = (request.form.get("follow_up_notes") or "").strip() or None
        entry.gc_awarded = (request.form.get("gc_awarded") or "").strip() or None
        entry.amount_award = parse_optional_float(request.form.get("amount_award"), "Amount of Award", 1)
        log_action(user, "update", "bid_tracker_entry", entry.id)
        db.session.commit()
        flash("Bid tracker entry updated.", "success")
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "error")
    except Exception:
        db.session.rollback()
        app.logger.exception("Error updating bid tracker entry")
        flash("Error updating bid tracker entry. Please try again.", "error")
    return redirect(url_for("bid_tracker"))

@app.route("/add_equipment", methods=["GET", "POST"])
@login_required
def add_equipment(user):
    if request.method == "POST" and user.role != "admin":
        flash("Admin access required.", "error")
        return redirect(url_for("add_equipment"))
    if request.method == "GET":
        search = request.args.get("search", "").strip()
        equipment_type = request.args.get("type", "").strip()
        sort = request.args.get("sort", "type")

        query = Equipment.query.filter_by(admin_user_id=user.id)
        if search:
            like = f"%{search}%"
            query = query.filter(
                or_(
                    Equipment.type.ilike(like),
                    Equipment.code.ilike(like),
                    Equipment.make.ilike(like),
                    Equipment.model.ilike(like),
                    Equipment.vin_number.ilike(like),
                )
            )
        if equipment_type:
            query = query.filter(Equipment.type == equipment_type)

        if sort == "code":
            query = query.order_by(Equipment.code.asc())
        elif sort == "make":
            query = query.order_by(Equipment.make.asc())
        else:
            query = query.order_by(Equipment.type.asc(), Equipment.code.asc())

        equipment_list = query.all()
        equipment_types = [
            row[0]
            for row in db.session.query(Equipment.type)
            .filter_by(admin_user_id=user.id)
            .distinct()
            .order_by(Equipment.type.asc())
            .all()
        ]
        return render_template(
            "add_equipment.html",
            equipment_list=equipment_list,
            equipment_types=equipment_types,
            search=search,
            equipment_type=equipment_type,
            sort=sort,
        )
    elif request.method == "POST":
        code = request.form.get("code")
        equipment_type = request.form.get("type")
        vin_number = request.form.get("vin_number") 
        make = request.form.get("make")
        model = request.form.get("model")
        mileage = request.form.get("mileage")
        service_required = request.form.get("service_required")
        last_service_date = request.form.get("last_service_date")
        
        try:
            new_equipment = Equipment(
                admin_user_id=user.id,
                type=equipment_type,
                vin_number=vin_number,
                code=code,
                make=make,
                model=model,
                qr_token=secrets.token_urlsafe(16),
                mileage=int(mileage) if mileage else None,
                service_required=service_required,
                last_service_date=datetime.strptime(last_service_date, "%Y-%m-%d") if last_service_date else None
            )
            db.session.add(new_equipment)
            db.session.flush()
            log_action(user, "create", "equipment", new_equipment.id)
            db.session.commit()
            flash("Equipment added successfully!", "success")
            return redirect(url_for("add_equipment"))
        except IntegrityError:
            db.session.rollback()
            flash("VIN number must be unique.", "error")
            return redirect(url_for("add_equipment"))
        except Exception:
            db.session.rollback()
            app.logger.exception("Error adding equipment")
            flash("Error adding equipment. Please try again.", "error")
            return redirect(url_for("add_equipment"))

@app.route("/delete_equipment/<int:equipment_id>", methods=["POST"])
@admin_required
def delete_equipment(user, equipment_id):
    try:
        equipment = Equipment.query.filter_by(id=equipment_id, admin_user_id=user.id).first()
        if not equipment:
            flash("Equipment not found!", "error")
        else:
            Service.query.filter_by(equipment_id=equipment_id).delete()
            Repair.query.filter_by(equipment_id=equipment_id).delete()
            db.session.delete(equipment)
            log_action(user, "delete", "equipment", equipment.id)
            db.session.commit()
            flash("Equipment deleted successfully!", "success")
    except Exception:
        db.session.rollback()
        app.logger.exception("Error deleting equipment")
        flash("Error deleting equipment. Please try again.", "error")
    
    return redirect(url_for("add_equipment"))

@app.route("/new_service/<int:equipment_id>", methods=["GET", "POST"])
@login_required
def new_service(user, equipment_id):
    equipment = Equipment.query.filter_by(id=equipment_id, admin_user_id=user.id).first()
    if not equipment:
        flash("Equipment not found!", "error")
        return redirect(url_for("add_equipment"))
    
    if request.method == "GET":
        services = Service.query.filter_by(equipment_id=equipment_id).order_by(Service.date.desc()).all()
        service_ids = [service.id for service in services]
        attachments = (
            ServiceAttachment.query
            .filter(ServiceAttachment.service_id.in_(service_ids))
            .order_by(ServiceAttachment.uploaded_at.desc())
            .all()
            if service_ids else []
        )
        cost_items = (
            ServiceCostItem.query
            .filter(ServiceCostItem.service_id.in_(service_ids))
            .all()
            if service_ids else []
        )
        attachments_by_service = {}
        for attachment in attachments:
            attachments_by_service.setdefault(attachment.service_id, []).append(attachment)
        cost_items_by_service = {}
        for item in cost_items:
            cost_items_by_service.setdefault(item.service_id, []).append(item)
        recent_checkins = (
            EquipmentCheckIn.query
            .filter_by(equipment_id=equipment_id)
            .order_by(EquipmentCheckIn.created_at.desc())
            .limit(5)
            .all()
        )
        return render_template(
            "new_service.html",
            equipment=equipment,
            services=services,
            attachments_by_service=attachments_by_service,
            cost_items_by_service=cost_items_by_service,
            recent_checkins=recent_checkins,
        )
    elif request.method == "POST":
        date = request.form.get("date")
        performed_by = request.form.get("performed_by")
        mileage = request.form.get("mileage")
        next_service = request.form.get("next_service")
        notes = request.form.get("notes")
        item_descriptions = request.form.getlist("cost_item_desc")
        item_amounts = request.form.getlist("cost_item_amount")
        
        try:
            cost_items, total_cost = parse_cost_items(item_descriptions, item_amounts)
            new_service_record = Service(
                equipment_id=equipment_id,
                date=datetime.strptime(date, "%Y-%m-%d").date() if date else None,
                performed_by=performed_by,
                mileage=int(mileage) if mileage else None,
                next_service=datetime.strptime(next_service, "%Y-%m-%d").date() if next_service else None,
                service_cost=total_cost if cost_items else None,
                notes=notes
            )
            db.session.add(new_service_record)
            db.session.flush()
            for desc, amount in cost_items:
                db.session.add(ServiceCostItem(service_id=new_service_record.id, description=desc, amount=amount))
            attachments = store_attachments(
                request.files.getlist("attachments"),
                {"service_id": new_service_record.id},
                ServiceAttachment,
            )
            for attachment in attachments:
                db.session.add(attachment)
            if date:
                equipment.last_service_date = datetime.strptime(date, "%Y-%m-%d").date()
            if mileage:
                equipment.mileage = int(mileage)
            log_action(user, "create", "service", new_service_record.id, f"equipment_id={equipment_id}")
            db.session.commit()
            flash("Service recorded successfully!", "success")
            return redirect(url_for("new_service", equipment_id=equipment_id))
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "error")
            return redirect(url_for("new_service", equipment_id=equipment_id))
        except Exception:
            db.session.rollback()
            app.logger.exception("Error recording service")
            flash("Error recording service. Please try again.", "error")
            return redirect(url_for("new_service", equipment_id=equipment_id))        


@app.route("/new_repair/<int:equipment_id>", methods=["GET", "POST"])
@login_required
def new_repair(user, equipment_id):
    equipment = Equipment.query.filter_by(id=equipment_id, admin_user_id=user.id).first()
    if not equipment:
        flash("Equipment was not found!", "error")
        return redirect(url_for("add_equipment"))
    if request.method == "GET":
        repairs = Repair.query.filter_by(equipment_id=equipment_id).order_by(Repair.date.desc()).all()
        repair_ids = [repair.id for repair in repairs]
        attachments = (
            RepairAttachment.query
            .filter(RepairAttachment.repair_id.in_(repair_ids))
            .order_by(RepairAttachment.uploaded_at.desc())
            .all()
            if repair_ids else []
        )
        cost_items = (
            RepairCostItem.query
            .filter(RepairCostItem.repair_id.in_(repair_ids))
            .all()
            if repair_ids else []
        )
        attachments_by_repair = {}
        for attachment in attachments:
            attachments_by_repair.setdefault(attachment.repair_id, []).append(attachment)
        cost_items_by_repair = {}
        for item in cost_items:
            cost_items_by_repair.setdefault(item.repair_id, []).append(item)
        recent_checkins = (
            EquipmentCheckIn.query
            .filter_by(equipment_id=equipment_id)
            .order_by(EquipmentCheckIn.created_at.desc())
            .limit(5)
            .all()
        )
        return render_template(
            "new_repair.html",
            equipment=equipment,
            repairs=repairs,
            attachments_by_repair=attachments_by_repair,
            cost_items_by_repair=cost_items_by_repair,
            recent_checkins=recent_checkins,
        )
    else:
        date = request.form.get("date")
        performed_by = request.form.get("performed_by")
        mileage = request.form.get("mileage")
        notes = request.form.get("notes")
        item_descriptions = request.form.getlist("cost_item_desc")
        item_amounts = request.form.getlist("cost_item_amount")
        try:
            cost_items, total_cost = parse_cost_items(item_descriptions, item_amounts)
            new_repair_record = Repair(
                equipment_id=equipment_id,
                date=datetime.strptime(date, "%Y-%m-%d").date() if date else None,
                performed_by=performed_by,
                mileage=int(mileage) if mileage else None,
                repair_cost=total_cost if cost_items else None,
                notes=notes
            )
            db.session.add(new_repair_record)
            db.session.flush()
            for desc, amount in cost_items:
                db.session.add(RepairCostItem(repair_id=new_repair_record.id, description=desc, amount=amount))
            attachments = store_attachments(
                request.files.getlist("attachments"),
                {"repair_id": new_repair_record.id},
                RepairAttachment,
            )
            for attachment in attachments:
                db.session.add(attachment)
            if mileage:
                equipment.mileage = int(mileage)
            log_action(user, "create", "repair", new_repair_record.id, f"equipment_id={equipment_id}")
            db.session.commit()
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "error")
            return redirect(url_for("new_repair", equipment_id=equipment_id))
        except Exception:
            db.session.rollback()
            app.logger.exception("Error recording repair")
            flash("Error recording repair. Please try again.", "error")
            return redirect(url_for("new_repair", equipment_id=equipment_id))
        flash("Repair recorded successfully!", "success")
        return redirect(url_for("new_repair", equipment_id=equipment_id))

@app.route("/service-attachment/<int:attachment_id>")
@login_required
def download_service_attachment(user, attachment_id):
    attachment = ServiceAttachment.query.filter_by(id=attachment_id).first()
    if not attachment:
        flash("Attachment not found.", "error")
        return redirect(url_for("dashboard"))
    service = Service.query.filter_by(id=attachment.service_id).first()
    if not service:
        flash("Attachment not found.", "error")
        return redirect(url_for("dashboard"))
    equipment = Equipment.query.filter_by(id=service.equipment_id, admin_user_id=user.id).first()
    if not equipment:
        flash("Not authorized.", "error")
        return redirect(url_for("dashboard"))
    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        attachment.stored_name,
        as_attachment=True,
        download_name=attachment.original_name,
    )

@app.route("/service-attachment/<int:attachment_id>/view")
@login_required
def view_service_attachment(user, attachment_id):
    attachment = ServiceAttachment.query.filter_by(id=attachment_id).first()
    if not attachment:
        flash("Attachment not found.", "error")
        return redirect(url_for("dashboard"))
    service = Service.query.filter_by(id=attachment.service_id).first()
    if not service:
        flash("Attachment not found.", "error")
        return redirect(url_for("dashboard"))
    equipment = Equipment.query.filter_by(id=service.equipment_id, admin_user_id=user.id).first()
    if not equipment:
        flash("Not authorized.", "error")
        return redirect(url_for("dashboard"))
    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        attachment.stored_name,
        as_attachment=False,
        download_name=attachment.original_name,
    )

@app.route("/repair-attachment/<int:attachment_id>")
@login_required
def download_repair_attachment(user, attachment_id):
    attachment = RepairAttachment.query.filter_by(id=attachment_id).first()
    if not attachment:
        flash("Attachment not found.", "error")
        return redirect(url_for("dashboard"))
    repair = Repair.query.filter_by(id=attachment.repair_id).first()
    if not repair:
        flash("Attachment not found.", "error")
        return redirect(url_for("dashboard"))
    equipment = Equipment.query.filter_by(id=repair.equipment_id, admin_user_id=user.id).first()
    if not equipment:
        flash("Not authorized.", "error")
        return redirect(url_for("dashboard"))
    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        attachment.stored_name,
        as_attachment=True,
        download_name=attachment.original_name,
    )

@app.route("/repair-attachment/<int:attachment_id>/view")
@login_required
def view_repair_attachment(user, attachment_id):
    attachment = RepairAttachment.query.filter_by(id=attachment_id).first()
    if not attachment:
        flash("Attachment not found.", "error")
        return redirect(url_for("dashboard"))
    repair = Repair.query.filter_by(id=attachment.repair_id).first()
    if not repair:
        flash("Attachment not found.", "error")
        return redirect(url_for("dashboard"))
    equipment = Equipment.query.filter_by(id=repair.equipment_id, admin_user_id=user.id).first()
    if not equipment:
        flash("Not authorized.", "error")
        return redirect(url_for("dashboard"))
    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        attachment.stored_name,
        as_attachment=False,
        download_name=attachment.original_name,
    )

@app.route("/equipment/<int:equipment_id>/qr.png")
@login_required
def equipment_qr(user, equipment_id):
    equipment = Equipment.query.filter_by(id=equipment_id, admin_user_id=user.id).first()
    if not equipment:
        flash("Equipment not found.", "error")
        return redirect(url_for("add_equipment"))
    if not equipment.qr_token:
        equipment.qr_token = secrets.token_urlsafe(16)
        log_action(user, "update", "equipment", equipment.id, "generated_qr")
        db.session.commit()
    checkin_url = url_for("equipment_checkin", token=equipment.qr_token, _external=True)
    img = qrcode.make(checkin_url)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return Response(buffer.getvalue(), mimetype="image/png")

@app.route("/equipment/<int:equipment_id>/checkins", methods=["GET"])
@login_required
def equipment_checkins(user, equipment_id):
    equipment = Equipment.query.filter_by(id=equipment_id, admin_user_id=user.id).first()
    if not equipment:
        flash("Equipment not found.", "error")
        return redirect(url_for("add_equipment"))
    checkins = (
        EquipmentCheckIn.query
        .filter_by(equipment_id=equipment_id)
        .order_by(EquipmentCheckIn.created_at.desc())
        .all()
    )
    return render_template("checkins.html", equipment=equipment, checkins=checkins)

@app.route("/checkin/<token>", methods=["GET", "POST"])
def equipment_checkin(token):
    equipment = Equipment.query.filter_by(qr_token=token).first()
    if not equipment:
        flash("Invalid or expired check-in link.", "error")
        return redirect(url_for("index"))
    if request.method == "GET":
        return render_template("checkin.html", equipment=equipment)

    mileage = request.form.get("mileage")
    issues = request.form.get("issues")
    try:
        checkin = EquipmentCheckIn(
            equipment_id=equipment.id,
            mileage=int(mileage) if mileage else None,
            issues=issues,
        )
        db.session.add(checkin)
        if mileage:
            equipment.mileage = int(mileage)
        log_action(None, "checkin", "equipment", equipment.id, "qr")
        db.session.commit()
        flash("Check-in submitted. Thank you!", "success")
        return redirect(url_for("equipment_checkin", token=token))
    except Exception:
        db.session.rollback()
        app.logger.exception("Error saving check-in")
        flash("Error submitting check-in. Please try again.", "error")
        return redirect(url_for("equipment_checkin", token=token))

@app.route("/equipment/<int:equipment_id>/report.csv", methods=["GET"])
@login_required
def equipment_report(user, equipment_id):
    equipment = Equipment.query.filter_by(id=equipment_id, admin_user_id=user.id).first()
    if not equipment:
        flash("Equipment was not found!", "error")
        return redirect(url_for("add_equipment"))

    services = Service.query.filter_by(equipment_id=equipment_id).order_by(Service.date.desc()).all()
    repairs = Repair.query.filter_by(equipment_id=equipment_id).order_by(Repair.date.desc()).all()
    service_ids = [service.id for service in services]
    repair_ids = [repair.id for repair in repairs]
    service_items = (
        ServiceCostItem.query
        .filter(ServiceCostItem.service_id.in_(service_ids))
        .all()
        if service_ids else []
    )
    repair_items = (
        RepairCostItem.query
        .filter(RepairCostItem.repair_id.in_(repair_ids))
        .all()
        if repair_ids else []
    )
    service_items_by_id = {}
    for item in service_items:
        service_items_by_id.setdefault(item.service_id, []).append(item)
    repair_items_by_id = {}
    for item in repair_items:
        repair_items_by_id.setdefault(item.repair_id, []).append(item)

    buffer = io.StringIO()
    writer = csv.writer(buffer)

    writer.writerow(["Equipment Report"])
    writer.writerow([])
    writer.writerow(["Code", sanitize_csv_value(equipment.code)])
    writer.writerow(["Type", sanitize_csv_value(equipment.type)])
    writer.writerow(["VIN", sanitize_csv_value(equipment.vin_number)])
    writer.writerow(["Make", sanitize_csv_value(equipment.make)])
    writer.writerow(["Model", sanitize_csv_value(equipment.model)])
    writer.writerow(["Mileage", sanitize_csv_value(equipment.mileage or "")])
    writer.writerow(["Service Required", sanitize_csv_value(equipment.service_required or "")])
    writer.writerow(["Last Service Date", sanitize_csv_value(equipment.last_service_date or "")])
    writer.writerow([])

    writer.writerow(["Services"])
    writer.writerow(["Date", "Performed By", "Mileage", "Next Service", "Cost", "Cost Items", "Notes"])
    for service in services:
        items = service_items_by_id.get(service.id, [])
        items_text = "; ".join([f"{item.description} (${item.amount:.2f})" for item in items])
        writer.writerow(
            [
                sanitize_csv_value(service.date),
                sanitize_csv_value(service.performed_by),
                sanitize_csv_value(service.mileage or ""),
                sanitize_csv_value(service.next_service or ""),
                sanitize_csv_value(service.service_cost or ""),
                sanitize_csv_value(items_text),
                sanitize_csv_value(service.notes or ""),
            ]
        )
    writer.writerow([])

    writer.writerow(["Repairs"])
    writer.writerow(["Date", "Performed By", "Mileage", "Cost", "Cost Items", "Notes"])
    for repair in repairs:
        items = repair_items_by_id.get(repair.id, [])
        items_text = "; ".join([f"{item.description} (${item.amount:.2f})" for item in items])
        writer.writerow(
            [
                sanitize_csv_value(repair.date),
                sanitize_csv_value(repair.performed_by),
                sanitize_csv_value(repair.mileage or ""),
                sanitize_csv_value(repair.repair_cost or ""),
                sanitize_csv_value(items_text),
                sanitize_csv_value(repair.notes or ""),
            ]
        )

    filename = f"{equipment.code}_report.csv".replace(" ", "_")
    response = Response(buffer.getvalue(), mimetype="text/csv")
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response
