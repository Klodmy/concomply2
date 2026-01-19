from flask import Flask, render_template, request, flash, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from models import AdminUser
from utils import hash_password, verify_password
from db import db, basedir
from dotenv import load_dotenv
import os

app = Flask(__name__)
load_dotenv()
app.secret_key = os.environ.get("SECRET_KEY")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(basedir, "db.db")
db.init_app(app)

@app.route("/dashboard", methods=["GET", "POST"])
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