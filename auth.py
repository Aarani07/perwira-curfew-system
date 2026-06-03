# auth.py
from flask import Blueprint, request, redirect, session, render_template, flash, url_for
from db import get_db
import pymysql

auth = Blueprint("auth", __name__)

@auth.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        conn = get_db()
        cur = conn.cursor(pymysql.cursors.DictCursor)

        # Check email + password (plain text)
        cur.execute("SELECT * FROM users WHERE email=%s AND password=%s", (email, password))
        user = cur.fetchone()
        cur.close()

        if not user:
            flash("Invalid email or password", "danger")
            return redirect(url_for("auth.login"))

        # Store user session
        session["user_id"] = user["user_id"]
        session["role"] = user["role"]
        session["name"] = user["name"]

        # Redirect based on role
        if user["role"] == "admin":
            return redirect(url_for("admin.dashboard"))
        elif user["role"] == "security":
            return redirect(url_for("security.dashboard"))
        elif user["role"] == "student":
            return redirect(url_for("student.dashboard"))

        flash("Role not recognized", "danger")
        return redirect(url_for("auth.login"))

    return render_template("login.html")

@auth.route("/logout")
def logout():
    session.clear()
    return redirect("/")
