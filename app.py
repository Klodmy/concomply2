from datetime import datetime
from flask import Flask, render_template, request, flash, redirect, url_for, session, send_file
from flask_sqlalchemy import SQLAlchemy
from models import AdminUser, Equipment, Service
from utils import hash_password, verify_password, pdfs
from db import db, basedir
from dotenv import load_dotenv
from openai import OpenAI
from json import dumps, loads
import os
import pdfplumber
from openpyxl import Workbook, load_workbook

app = Flask(__name__)
load_dotenv()
app.secret_key = os.environ.get("SECRET_KEY")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(basedir, "db.db")
db.init_app(app)

@app.route("/", methods=["GET", "POST"])
def dashboard():
    if request.method == "GET":
        try:
            user = AdminUser.query.filter_by(id=session.get("user_id")).first()
        except:
            flash("Please log in!")
            return redirect(url_for("login"))
        if user:
            return render_template("dashboard.html", user=user)
        else:
            flash("Please log in again!")
            return redirect(url_for("login"))
    else:
        pass
    

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")
    else:
        email = request.form.get("email")
        password = request.form.get("password")

        user = AdminUser.query.filter_by(email=email).first()
        if not user:
            flash("User not found!")
            return redirect(url_for("login"))

        if user and verify_password(password, user.password_hash):
            session["user_id"] = user.id
            return redirect("/dashboard")
        else:
            flash("Wrong password!")
            return redirect(url_for("login"))
        
@app.route("/logout")
def logout():
    session.pop("user_id", None)
    flash("Logged out successfully!")
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
            print(password, confirm_password)
            flash("Password do not match!", "error")
            return redirect(url_for("registration"))
        else:
            new_user = AdminUser(email=email, password_hash=hash_password(password))
            db.session.add(new_user)
            db.session.commit()
    
    return redirect(url_for("login"))

@app.route("/add_equipment", methods=["GET", "POST"])
def add_equipment():
    user = AdminUser.query.filter_by(id=session.get("user_id")).first()
    if not user:
        flash("Please log in!")
        return redirect(url_for("login"))
    
    if request.method == "GET":
        equipment_list = Equipment.query.filter_by(admin_user_id=user.id).all()
        return render_template("add_equipment.html", equipment_list=equipment_list)
    elif request.method == "POST":
        code = request.form.get("code")
        make = request.form.get("make")
        model = request.form.get("model")
        mileage = request.form.get("mileage")
        equipment_type = request.form.get("type")
        vin_number = request.form.get("vin_number")
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
                last_service_date=datetime.strptime(last_service_date, "%Y-%m-%d").date() if last_service_date else None
            )
            db.session.add(new_equipment)
            db.session.commit()
            flash("Equipment added successfully!", "success")
            return redirect(url_for("add_equipment"))
        except Exception as e:
            flash(f"Error adding equipment: {str(e)}", "error")
            return redirect(url_for("add_equipment"))

@app.route("/delete_equipment/<int:equipment_id>", methods=["POST"])
def delete_equipment(equipment_id):
    user = AdminUser.query.filter_by(id=session.get("user_id")).first()
    if not user:
        flash("Please log in!")
        return redirect(url_for("login"))
    
    try:
        equipment = Equipment.query.filter_by(id=equipment_id, admin_user_id=user.id).first()
        if not equipment:
            flash("Equipment not found!", "error")
        else:
            db.session.delete(equipment)
            db.session.commit()
            flash("Equipment deleted successfully!", "success")
    except Exception as e:
        flash(f"Error deleting equipment: {str(e)}", "error")
    
    return redirect(url_for("add_equipment"))

@app.route("/new_service/<int:equipment_id>", methods=["GET", "POST"])
def new_service(equipment_id):
    user = AdminUser.query.filter_by(id=session.get("user_id")).first()
    if not user:
        flash("Please log in!")
        return redirect(url_for("login"))
    
    equipment = Equipment.query.filter_by(id=equipment_id, admin_user_id=user.id).first()
    if not equipment:
        flash("Equipment not found!")
        return redirect(url_for("add_equipment"))
    
    if request.method == "GET":
        services = Service.query.filter_by(equipment_id=equipment_id).all()
        return render_template("new_service.html", equipment=equipment, services=services)
    elif request.method == "POST":
        date = request.form.get("date")
        performed_by = request.form.get("performed_by")
        mileage = request.form.get("mileage")
        next_service = request.form.get("next_service")
        
        try:
            new_service_record = Service(
                equipment_id=equipment_id,
                date=datetime.strptime(date, "%Y-%m-%d").date() if date else None,
                performed_by=performed_by,
                mileage=int(mileage) if mileage else None,
                next_service=datetime.strptime(next_service, "%Y-%m-%d").date() if next_service else None
            )
            db.session.add(new_service_record)
            db.session.commit()
            flash("Service recorded successfully!", "success")
            return redirect(url_for("new_service", equipment_id=equipment_id))
        except Exception as e:
            flash(f"Error recording service: {str(e)}", "error")
            return redirect(url_for("new_service", equipment_id=equipment_id))
        


@app.route("/quote_reader", methods=["GET", "POST"])
def quote_reader():
    user = AdminUser.query.filter_by(id=session.get("user_id")).first()
    if not user:
        flash("Please log in!")
        return redirect(url_for("login"))
    if request.method == "GET":
        return render_template("quote_reader.html")
    else:
        api_key = os.environ.get("OPENAI_API_KEY")
        openai_client = OpenAI(api_key=api_key)

        pdf_file = request.files.get("pdf_file")
        if not pdf_file:
            flash("No file uploaded!", "error")
            return redirect(url_for("quote_reader"))
        try:
            with pdfplumber.open(pdf_file) as pdf:
                text = ""
                for page in pdf.pages:
                    tables = page.extract_tables()
                    if tables:
                        for table in tables:
                            for row in table:
                                text += " | ".join(str(cell) if cell else "" for cell in row) + "\n"
                    else:
                        text += page.extract_text() + "\n"
                    print(text)
            question = request.form.get("question")
            response = openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": f"You are an assistant that summarizes schedule. {question}"},
                    {"role": "user", "content": f"Return JSON with the following structure: \
                     column - site - description - special_description - brokers (if any) - company_truck_drivers - employees - equipment. \
                    \n\n{text}"}
                ]
            )
            answer = response.choices[0].message.content
            return render_template("quote_reader.html", answer=answer)
        except Exception as e:
            flash(f"Error processing PDF: {str(e)}", "error")
    return render_template("quote_reader.html", answer=answer)

@app.route("/download/<filename>")
def download_file(filename):
    user = AdminUser.query.filter_by(id=session.get("user_id")).first()
    if not user:
        flash("Please log in!")
        return redirect(url_for("login"))
    
    try:
        filepath = os.path.join("C:\\Users\\IPAC\\Desktop\\FILES\\Scripts\\concomply2\\static", filename)
        return send_file(filepath, as_attachment=True)
    except Exception as e:
        flash(f"Error downloading file: {str(e)}", "error")
        return redirect(url_for("quote_reader"))


@app.route("/decoder", methods=["GET", "POST"])
def decoder():
    user = AdminUser.query.filter_by(id=session.get("user_id")).first()
    if not user:
        flash("Please log in!")
        return redirect(url_for("login"))
    
    if request.method == "GET":
        return render_template("decoder.html")
    else:
        api_key = os.environ.get("OPENAI_API_KEY")
        openai_client = OpenAI(api_key=api_key)

        audio_file = request.files.get("audio_file")
        if not audio_file:
            flash("No file uploaded!", "error")
            return redirect(url_for("decoder"))
        try:
            import whisper
            # Save uploaded file temporarily
            temp_filepath = os.path.join("C:\\Users\\IPAC\\Desktop\\FILES\\Scripts\\concomply2\\static", audio_file.filename)
            audio_file.save(temp_filepath)
            
            # Load Whisper model and transcribe
            model = whisper.load_model("base")
            result = model.transcribe(temp_filepath)
            transcription_text = result["text"]
            
            # Create text file
            text_filename = audio_file.filename.rsplit(".", 1)[0] + "_transcript.txt"
            text_filepath = os.path.join("C:\\Users\\IPAC\\Desktop\\FILES\\Scripts\\concomply2\\static", text_filename)
            
            with open(text_filepath, "w") as f:
                f.write(transcription_text)
            
            # Clean up temporary audio file
            os.remove(temp_filepath)
            
            flash("Audio decoded successfully!", "success")
            return render_template("decoder.html", transcript=transcription_text, text_filename=text_filename)
        except Exception as e:
            flash(f"Error processing audio: {str(e)}", "error")
            return redirect(url_for("decoder"))
