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
            # Convert PDF to markdown format optimized for LLMs
            with pdfplumber.open(pdf_file) as pdf:
                markdown_content = "# PDF Document\n\n"
                
                for page_num, page in enumerate(pdf.pages, 1):
                    markdown_content += f"## Page {page_num}\n\n"
                    
                    # Extract text with structure
                    text = page.extract_text()
                    if text:
                        markdown_content += text + "\n\n"
                    
                    # Extract tables if present
                    tables = page.extract_tables()
                    if tables:
                        for table_idx, table in enumerate(tables, 1):
                            markdown_content += f"### Table {table_idx}\n\n"
                            if table:
                                # Create markdown table
                                headers = table[0] if table else []
                                markdown_content += "| " + " | ".join(str(h) if h else "" for h in headers) + " |\n"
                                markdown_content += "|" + "|".join(["---" for _ in headers]) + "|\n"
                                
                                for row in table[1:]:
                                    markdown_content += "| " + " | ".join(str(cell) if cell else "" for cell in row) + " |\n"
                                markdown_content += "\n"
            
            # Send markdown to LLM for extraction
            response = openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an assistant that extracts structured information from documents and provides responses in valid JSON format only. No markdown, no code blocks, only JSON."},
                    {"role": "user", "content": f"Extract the following information from this quote document and return ONLY valid JSON:\n- company_name\n- company_address\n- contact_person\n- contact_cell\n- contact_email\n- quote_items (array with: quantity, units_of_measure, description, unit_price, total_price)\n- subtotal\n- tax_amount\n- total_amount\n\nDocument:\n{markdown_content}"}
                ]
            )
            response_text = response.choices[0].message.content.strip()
            
            # Remove markdown code blocks if present
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            
            response_text = response_text.strip()
            print(f"DEBUG: Response text: {response_text}")  # Debug log
            
            summary = loads(response_text)
        except ValueError as e:
            print(f"DEBUG: JSON Parse Error - {str(e)}")
            flash(f"Error parsing PDF response as JSON: {str(e)}", "error")
            return redirect(url_for("quote_reader"))
        except Exception as e:
            print(f"DEBUG: General Error - {str(e)}")
            flash(f"Error processing PDF: {str(e)}", "error")
            return redirect(url_for("quote_reader"))
        
        wb = load_workbook("C:\\Users\\IPAC\\Desktop\\FILES\\Scripts\\concomply2\\static\\IPAC_PO_Sub.xlsx", read_only=False, data_only=False)
        ws = wb.active
        
        ws["C14"] = summary.get("company_name", "")
        ws["C15"] = summary.get("company_address", "")
        ws["I14"] = summary.get("contact_person", "")
        ws["I15"] = summary.get("contact_cell", "")
        ws["I16"] = summary.get("contact_email", "")
        for idx, item in enumerate(summary.get("quote_items", []), start=0):
            ws[f"A{19 + idx}"] = item.get("item_number", "")
            ws[f"B{19 + idx}"] = item.get("units_of_measure", "")
            ws[f"C{19 + idx}"] = item.get("description", "")
            ws[f"I{19 + idx}"] = item.get("unit_price", "")
            ws[f"J{19 + idx}"] = item.get("total_price", "")
        ws["J40"] = summary.get("subtotal", "")
        
        
        filename = f"{summary.get('company_name', 'Quote').replace('/', '_').replace('\\', '_')}.xlsx"
        filepath = os.path.join("C:\\Users\\IPAC\\Desktop\\FILES\\Scripts\\concomply2\\static", filename)
        wb.save(filepath)
        
        return render_template("quote_reader.html", summary=summary, filename=filename)

    return render_template("quote_reader.html")

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