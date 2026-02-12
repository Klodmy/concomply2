from datetime import datetime
import csv
import io
import os
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, render_template, request, flash, redirect, url_for, session, Response
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from db import db, basedir
from models import AdminUser, Equipment, Service, Repair
from utils import hash_password, verify_password

app = Flask(__name__)
load_dotenv()
app.secret_key = os.environ.get("SECRET_KEY")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(basedir, "db.db")
db.init_app(app)

def login_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        user = AdminUser.query.filter_by(id=session.get("user_id")).first()
        if not user:
            flash("Please log in!", "error")
            return redirect(url_for("login"))
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
            new_user = AdminUser(email=email, password_hash=hash_password(password))
            db.session.add(new_user)
            db.session.commit()
    
    return redirect(url_for("login"))

@app.route("/add_equipment", methods=["GET", "POST"])
@login_required
def add_equipment(user):
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
                mileage=int(mileage) if mileage else None,
                service_required=service_required,
                last_service_date=datetime.strptime(last_service_date, "%Y-%m-%d") if last_service_date else None
            )
            db.session.add(new_equipment)
            db.session.commit()
            flash("Equipment added successfully!", "success")
            return redirect(url_for("add_equipment"))
        except IntegrityError:
            db.session.rollback()
            flash("VIN number must be unique.", "error")
            return redirect(url_for("add_equipment"))
        except Exception as e:
            db.session.rollback()
            flash(f"Error adding equipment: {str(e)}", "error")
            return redirect(url_for("add_equipment"))

@app.route("/delete_equipment/<int:equipment_id>", methods=["POST"])
@login_required
def delete_equipment(user, equipment_id):
    try:
        equipment = Equipment.query.filter_by(id=equipment_id, admin_user_id=user.id).first()
        if not equipment:
            flash("Equipment not found!", "error")
        else:
            Service.query.filter_by(equipment_id=equipment_id).delete()
            Repair.query.filter_by(equipment_id=equipment_id).delete()
            db.session.delete(equipment)
            db.session.commit()
            flash("Equipment deleted successfully!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting equipment: {str(e)}", "error")
    
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
        return render_template("new_service.html", equipment=equipment, services=services)
    elif request.method == "POST":
        date = request.form.get("date")
        performed_by = request.form.get("performed_by")
        mileage = request.form.get("mileage")
        next_service = request.form.get("next_service")
        service_cost = request.form.get("service_cost")
        notes = request.form.get("notes")
        
        try:
            new_service_record = Service(
                equipment_id=equipment_id,
                date=datetime.strptime(date, "%Y-%m-%d").date() if date else None,
                performed_by=performed_by,
                mileage=int(mileage) if mileage else None,
                next_service=datetime.strptime(next_service, "%Y-%m-%d").date() if next_service else None,
                service_cost=float(service_cost) if service_cost else None,
                notes=notes
            )
            db.session.add(new_service_record)
            if date:
                equipment.last_service_date = datetime.strptime(date, "%Y-%m-%d").date()
            if mileage:
                equipment.mileage = int(mileage)
            db.session.commit()
            flash("Service recorded successfully!", "success")
            return redirect(url_for("new_service", equipment_id=equipment_id))
        except Exception as e:
            db.session.rollback()
            flash(f"Error recording service: {str(e)}", "error")
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
        return render_template("new_repair.html", equipment=equipment, repairs=repairs)
    else:
        date = request.form.get("date")
        performed_by = request.form.get("performed_by")
        mileage = request.form.get("mileage")
        repair_cost = request.form.get("repair_cost")
        notes = request.form.get("notes")
        try:
            new_repair_record = Repair(
                equipment_id=equipment_id,
                date=datetime.strptime(date, "%Y-%m-%d").date() if date else None,
                performed_by=performed_by,
                mileage=int(mileage) if mileage else None,
                repair_cost=float(repair_cost) if repair_cost else None,
                notes=notes
            )
            db.session.add(new_repair_record)
            if mileage:
                equipment.mileage = int(mileage)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            flash(f"Error: {e}", "error")
            return redirect(url_for("new_repair", equipment_id=equipment_id))
        flash("Repair recorded successfully!", "success")
        return redirect(url_for("new_repair", equipment_id=equipment_id))

@app.route("/equipment/<int:equipment_id>/report.csv", methods=["GET"])
@login_required
def equipment_report(user, equipment_id):
    equipment = Equipment.query.filter_by(id=equipment_id, admin_user_id=user.id).first()
    if not equipment:
        flash("Equipment was not found!", "error")
        return redirect(url_for("add_equipment"))

    services = Service.query.filter_by(equipment_id=equipment_id).order_by(Service.date.desc()).all()
    repairs = Repair.query.filter_by(equipment_id=equipment_id).order_by(Repair.date.desc()).all()

    buffer = io.StringIO()
    writer = csv.writer(buffer)

    writer.writerow(["Equipment Report"])
    writer.writerow([])
    writer.writerow(["Code", equipment.code])
    writer.writerow(["Type", equipment.type])
    writer.writerow(["VIN", equipment.vin_number])
    writer.writerow(["Make", equipment.make])
    writer.writerow(["Model", equipment.model])
    writer.writerow(["Mileage", equipment.mileage or ""])
    writer.writerow(["Service Required", equipment.service_required or ""])
    writer.writerow(["Last Service Date", equipment.last_service_date or ""])
    writer.writerow([])

    writer.writerow(["Services"])
    writer.writerow(["Date", "Performed By", "Mileage", "Next Service", "Cost", "Notes"])
    for service in services:
        writer.writerow(
            [
                service.date,
                service.performed_by,
                service.mileage or "",
                service.next_service or "",
                service.service_cost or "",
                service.notes or "",
            ]
        )
    writer.writerow([])

    writer.writerow(["Repairs"])
    writer.writerow(["Date", "Performed By", "Mileage", "Cost", "Notes"])
    for repair in repairs:
        writer.writerow(
            [
                repair.date,
                repair.performed_by,
                repair.mileage or "",
                repair.repair_cost or "",
                repair.notes or "",
            ]
        )

    filename = f"{equipment.code}_report.csv".replace(" ", "_")
    response = Response(buffer.getvalue(), mimetype="text/csv")
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response
