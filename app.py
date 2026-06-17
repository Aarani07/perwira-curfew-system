import os
import io
import re
import random
import string
import pymysql
import smtplib
import csv
import cv2
import json
import base64
import secrets 
import face_recognition 
import numpy as np
import uuid
import time
import hmac
import hashlib
import qrcode
import pdfkit
import stripe
import requests
import resend
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from functools import wraps
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, jsonify, make_response
)
from flask import send_file, abort
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
load_dotenv(dotenv_path=".env", override=True)
from email.message import EmailMessage
from db import get_db, init_db
from io import StringIO
from io import BytesIO
from flask import Response
from PIL import Image
from flask import request
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad, unpad

# =========================
# CREATE APP (THIS MUST COME FIRST)
# =========================
app = Flask(__name__)
app.config["SECRET_KEY"] = "f7f0a1855e98d7726d138f93418b7f31f3cd037fee119a027860c99a8dda3bb5"
app.permanent_session_lifetime = timedelta(minutes=15)

AES_KEY = hashlib.sha256(
    b"PRCDS_FACE_EMBEDDING_SECRET_KEY"
).digest()

# =========================================
# SESSION TIMEOUT (15 MINUTES INACTIVE)
# =========================================
@app.before_request
def session_management():

    session.permanent = True

    now = datetime.now()

    if "last_activity" in session:

        last_activity = datetime.fromisoformat(
            session["last_activity"]
        )

        if now - last_activity > timedelta(minutes=15):

            session.clear()

            flash(
                "Your session has expired due to inactivity. Please log in again.",
                "warning"
            )

            return redirect(url_for("login"))

    session["last_activity"] = now.isoformat()

# =========================
# CONFIG / CONSTANTS
# =========================
ALLOWED_APPEAL_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "doc"}
MAX_APPEAL_FILE_SIZE = 5 * 1024 * 1024  # 5MB

# =========================
# CREATE APP (THIS MUST COME FIRST)
# =========================
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

def allowed_appeal_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_APPEAL_EXTENSIONS

# ======================================================
# PASSWORD VALIDATION
# ======================================================
def validate_password(password):
    return (
        len(password) >= 8 and
        re.search(r"[A-Z]", password) and
        re.search(r"[a-z]", password) and
        re.search(r"[0-9]", password) and
        re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?]", password)
    )

def send_otp_email(to_email, otp):

    resend.Emails.send({
        "from": "onboarding@resend.dev",
        "to": ["kklkcurfewsystem25@gmail.com"],
        "subject": "Password Reset Verification Code",
        "html": f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; color: #333;">
            
            <h2 style="color: #0d6efd;">
                Perwira Residential Curfew Detection System
            </h2>

            <p>Dear User,</p>

            <p>
                We have received a request to reset the password associated with your account.
                To proceed with the password reset process, please use the One-Time Password (OTP) provided below:
            </p>

            <div style="
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                padding: 20px;
                text-align: center;
                margin: 25px 0;
            ">
                <h1 style="
                    margin: 0;
                    color: #0d6efd;
                    letter-spacing: 5px;
                ">
                    {otp}
                </h1>
            </div>

            <p>
                This OTP is required to verify your identity and complete the password reset process.
            </p>

            <p>
                If you did not request a password reset, please ignore this email. No changes will be made to your account.
            </p>

            <hr>

            <p style="font-size: 12px; color: #6c757d;">
                This is an automated message from the Perwira Residential Curfew Detection System.
                Please do not reply to this email.
            </p>

        </div>
        """
    })

def send_warning_letter_email(
    to_email,
    student_name,
    warning_no,
    violation_date
):

    resend.Emails.send({
        "from": "onboarding@resend.dev",
        "to": ["kklkcurfewsystem25@gmail.com"],  # Change to [to_email] after domain verification
        "subject": f"Official Warning Letter Notification - {warning_no}",
        "html": f"""
        <div style="font-family: Arial, sans-serif; max-width: 700px; margin: auto; color: #333;">

            <h2 style="color: #dc3545;">
                Perwira Residential Curfew Detection System
            </h2>

            <p>Dear <strong>{student_name}</strong>,</p>

            <p>
                This email serves as an official notification that a warning letter has been issued
                regarding a violation of the residential curfew regulations.
            </p>

            <div style="
                background-color: #fff3cd;
                border-left: 5px solid #ffc107;
                padding: 15px;
                margin: 20px 0;
            ">
                <p><strong>Warning Letter Number:</strong> {warning_no}</p>
                <p><strong>Violation Date:</strong> {violation_date}</p>
            </div>

            <p>
                You are required to log in to the Perwira Residential Curfew Detection System (PRCDS)
                to review and acknowledge this warning letter.
            </p>

            <p>
                Failure to acknowledge the warning letter may result in additional disciplinary action
                in accordance with residential regulations.
            </p>

            <p>
                If you believe this notification was issued in error, please contact the Residential
                Management Office immediately for clarification.
            </p>

            <br>

            <p>
                Regards,<br>
                <strong>Residential Management Office</strong><br>
                Perwira Residential Curfew Detection System (PRCDS)<br>
                Universiti Tun Hussein Onn Malaysia (UTHM)
            </p>

            <hr>

            <p style="font-size: 12px; color: #6c757d;">
                This is an automated message generated by the Perwira Residential Curfew Detection System.
                Please do not reply directly to this email.
            </p>

        </div>
        """
    })

def encrypt_embedding(data):

    cipher = AES.new(
        AES_KEY,
        AES.MODE_GCM
    )

    ciphertext, tag = cipher.encrypt_and_digest(
        data.encode()
    )

    encrypted_blob = base64.b64encode(
        cipher.nonce +
        tag +
        ciphertext
    ).decode()

    return encrypted_blob


def decrypt_embedding(encrypted_blob):

    raw = base64.b64decode(
        encrypted_blob
    )

    nonce = raw[:16]
    tag = raw[16:32]
    ciphertext = raw[32:]

    cipher = AES.new(
        AES_KEY,
        AES.MODE_GCM,
        nonce=nonce
    )

    plaintext = cipher.decrypt_and_verify(
        ciphertext,
        tag
    )

    return plaintext.decode()

# ======================================================
# APP FACTORY
# ======================================================
def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["SECRET_KEY"] = os.getenv(
    "SECRET_KEY",
    "f7f0a1855e98d7726d138f93418b7f31f3cd037fee119a027860c99a8dda3bb5"
)

    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=False,  # True after HTTPS deployment
        SESSION_COOKIE_SAMESITE="Lax"
    )
    app.config["UPLOAD_FOLDER"] = "static/images/profiles"
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    FACE_DATASET_DIR = "static/faces"
    TRAINER_DIR = "static/trainer"
    TEMP_DIR = "static/temp"
    MODEL_PATH = os.path.join(TRAINER_DIR, "face_trainer.yml")

    os.makedirs(FACE_DATASET_DIR, exist_ok=True)
    os.makedirs(TRAINER_DIR, exist_ok=True)
    os.makedirs(TEMP_DIR, exist_ok=True)

    # ==========================
    # 📁 FILE UPLOAD SETTINGS
    # ==========================
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}

    def allowed_file(filename):
        return "." in filename and \
            filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

    def get_face_detector():
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        return cv2.CascadeClassifier(cascade_path)

    init_db(app)

    # ==================================================
    # LOGIN REQUIRED DECORATOR
    # ==================================================
    def login_required(role=None):
        def decorator(f):
            @wraps(f)
            def wrapped(*args, **kwargs):
                if role:
                    if f"{role}_user_id" not in session:
                        return redirect(url_for("login"))

                    session["active_role"] = role

                    return f(*args, **kwargs)
                
                active_user = get_active_user()

                if not active_user:
                    return redirect(url_for("login"))

                return f(*args, **kwargs)
            
            return wrapped
        return decorator
    
    def get_current_user(role):
        return {
            "user_id": session.get(f"{role}_user_id"),
            "name": session.get(f"{role}_name")
        }

    def get_active_user():

        role = session.get("active_role")

        if not role:
            return None

        return {
            "role": role,
            "user_id": session.get(f"{role}_user_id"),
            "name": session.get(f"{role}_name")
        }
    
    @app.context_processor
    def inject_active_user():

        active_user = get_active_user()

        return {
            "active_user": active_user
        }
    
    @app.route("/switch-active-role", methods=["POST"])
    def switch_active_role():

        data = request.get_json()

        role = data.get("role")

        if role:
            session["active_role"] = role

        return jsonify({"success": True})

    # ==================================================
    # NOTIFICATION HELPERS
    # ==================================================
    def create_notification(
        cur,
        user_id,
        title,
        message,
        notif_type,
        related_violation_id=None,
        related_appeal_id=None
    ):

        # =========================================
        # PREVENT DUPLICATES
        # =========================================
        cur.execute("""
            SELECT notification_id
            FROM system_notifications
            WHERE user_id = %s
            AND title = %s
            AND type = %s

            AND (
                (related_violation_id IS NOT NULL AND related_violation_id = %s)
                OR
                (related_appeal_id IS NOT NULL AND related_appeal_id = %s)
                OR
                (
                    related_violation_id IS NULL
                    AND related_appeal_id IS NULL
                    AND message = %s
                )
            )

            LIMIT 1
        """, (
            user_id,
            title,
            notif_type,
            related_violation_id,
            related_appeal_id,
            message
        ))

        existing = cur.fetchone()

        # skip duplicate
        if existing:
            return

        # =========================================
        # INSERT NOTIFICATION
        # =========================================
        cur.execute("""
            INSERT INTO system_notifications (
                user_id,
                title,
                message,
                type,
                related_violation_id,
                related_appeal_id,
                is_read,
                created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, 0, NOW())
        """, (
            user_id,
            title,
            message,
            notif_type,
            related_violation_id,
            related_appeal_id
        ))

    def notify_role(
        cur,
        role,
        title,
        message,
        notif_type,
        related_violation_id=None,
        related_appeal_id=None
    ):

        cur.execute("""
            SELECT user_id
            FROM users
            WHERE role = %s
        """, (role,))

        users = cur.fetchall()

        for user in users:

            uid = user["user_id"] if isinstance(user, dict) else user[0]

            create_notification(
                cur,
                uid,
                title,
                message,
                notif_type,
                related_violation_id,
                related_appeal_id
            )

    def notify_user(cur, user_id, title, message, notif_type,
                    related_violation_id=None, related_appeal_id=None):
        create_notification(
            cur,
            user_id,
            title,
            message,
            notif_type,
            related_violation_id,
            related_appeal_id
        )

    def notify_all_users(cur, title, message, notif_type,
                         related_violation_id=None, related_appeal_id=None):
        
        cur.execute("SELECT user_id FROM users")
        users = cur.fetchall()

        for user in users:
            uid = user["user_id"] if isinstance(user, dict) else user[0]
            create_notification(
                cur,
                uid,
                title,
                message,
                notif_type,
                related_violation_id,
                related_appeal_id
            )

    def get_unread_notification_count(cur, user_id):
        cur.execute("""
            SELECT COUNT(*) AS total
            FROM system_notifications
            WHERE user_id = %s
              AND is_read = 0
        """, (user_id,))
        row = cur.fetchone()
        return row["total"] if row else 0

    def get_latest_notifications(cur, user_id, limit=5):
        cur.execute("""
            SELECT
                notification_id,
                title,
                message,
                type,
                is_read,
                created_at,
                related_violation_id,
                related_appeal_id
            FROM system_notifications
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT %s
        """, (user_id, limit))
        return cur.fetchall()
    
    # ==================================================
    # WEEKLY WARNING LETTER GENERATION
    # ==================================================
    def generate_weekly_warning_letters():

        conn = get_db()
        cur = conn.cursor(pymysql.cursors.DictCursor)

        try:

            # violations older than 7 days
            # still unresolved/unexcused
            cur.execute("""

                SELECT *
                FROM violations v

                WHERE v.status = 'Unexcused'

                AND DATEDIFF(NOW(), v.violation_date) >= 7

                AND v.violation_id NOT IN (

                    SELECT violation_id
                    FROM warning_letters
                    WHERE violation_id IS NOT NULL

                )

            """)

            violations = cur.fetchall()

            for v in violations:

                violation_id = v["violation_id"]

                # =========================================
                # CHECK APPEAL STATUS
                # =========================================
                cur.execute("""

                    SELECT status
                    FROM appeals

                    WHERE violation_id = %s

                    ORDER BY submitted_at DESC

                    LIMIT 1

                """, (violation_id,))

                appeal = cur.fetchone()

                # =========================================
                # IF APPEAL APPROVED
                # DELETE WARNING LETTER IF EXISTS
                # =========================================
                if appeal and appeal["status"] == "Approved":

                    cur.execute("""

                        DELETE FROM warning_letters
                        WHERE violation_id = %s

                    """, (violation_id,))

                    conn.commit()

                    print(
                        f"✅ Warning letter removed for "
                        f"violation {violation_id}"
                    )

                    continue

                # =========================================
                # IF APPEAL PENDING
                # SKIP GENERATION
                # =========================================
                if appeal and appeal["status"] == "Pending":

                    print(
                        f"⏳ Appeal still pending for "
                        f"violation {violation_id}"
                    )

                    continue

                # =========================================
                # CHECK EXISTING WARNING LETTER AGAIN
                # EXTRA SAFETY
                # =========================================
                cur.execute("""

                    SELECT warning_id
                    FROM warning_letters

                    WHERE violation_id = %s

                """, (violation_id,))

                existing_warning = cur.fetchone()

                if existing_warning:

                    print(
                        f"⚠ Warning letter already exists "
                        f"for violation {violation_id}"
                    )

                    continue

                # =========================================
                # GENERATE WARNING LETTER
                # =========================================
                reason = (
                    "Unexcused curfew violation "
                    "after 7 days."
                )

                cur.execute("""

                    INSERT INTO warning_letters (
                        user_id,
                        violation_id,
                        issued_at,
                        violation_count,
                        reason,
                        warning_letter_status
                    )

                    VALUES (
                        %s,
                        %s,
                        NOW(),
                        %s,
                        %s,
                        'Draft'
                    )

                """, (
                    v["user_id"],
                    v["violation_id"],
                    1,
                    reason
                ))

                warning_id = cur.lastrowid

                # notify admin
                notify_role(
                    cur,
                    "admin",
                    "Warning Letter Generated",
                    "A warning letter has been generated.",
                    "warning_letter",
                    related_violation_id=violation_id
                )

                # STUDENT
                notify_user(
                    cur,
                    v["user_id"],
                    "Warning Letter Issued",
                    "A warning letter has been generated for you.",
                    "warning_letter"
                )

                print(
                    f"✅ Warning letter generated for "
                    f"violation {violation_id}"
                )

            conn.commit()

        finally:
            cur.close()

    def validate_official_photo(image_path):

        try:

            face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades +
                "haarcascade_frontalface_default.xml"
            )

            image = cv2.imread(image_path)

            if image is None:

                return (
                    False,
                    "Invalid image uploaded."
                )

            gray = cv2.cvtColor(
                image,
                cv2.COLOR_BGR2GRAY
            )

            faces = face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(100, 100)
            )

            # =========================
            # NO FACE DETECTED
            # =========================
            if len(faces) == 0:

                return (
                    False,
                    "No clear face detected. "
                    "Please upload an official passport-style photo."
                )

            # =========================
            # MULTIPLE FACES
            # =========================
            if len(faces) > 1:

                return (
                    False,
                    "Multiple faces detected. "
                    "Group photos are not allowed."
                )

            # =========================
            # FACE TOO FAR
            # =========================
            x, y, w, h = faces[0]

            image_height, image_width = image.shape[:2]

            face_ratio = (
                (w * h) /
                (image_width * image_height)
            )

            # stricter detection
            if face_ratio < 0.15:

                return (
                    False,
                    "Face is too far away. "
                    "Please upload a close-up passport-style photo."
                )

            return (
                True,
                "Valid official photo."
            )

        except Exception as e:

            print(
                "PHOTO VALIDATION ERROR:",
                e
            )

            return (
                False,
                "Unable to validate image."
            )

    def format_date_with_suffix(dt):
        if not dt:
            return "-"

        # 🔥 HANDLE STRING CASE
        if isinstance(dt, str):

            # ❌ invalid mysql date
            if dt == "0000-00-00 00:00:00":
                return "-"

            try:
                dt = datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")
            except:
                return "-"

        day = dt.day

        if 11 <= day <= 13:
            suffix = "th"
        else:
            suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")

        return dt.strftime(f"%d{suffix} %B %Y")

    def format_datetime(dt):
        if not dt:
            return "-", "-"
        
        # 🔥 FIX HERE ALSO
        if isinstance(dt, str):

            if dt == "0000-00-00 00:00:00":
                return "-", "-"

            try:
                dt = datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")
            except:
                return "-", "-"

        date_part = dt.strftime("%d %B %Y")
        time_part = dt.strftime("%I:%M %p")  # 11:51 PM

        return date_part, time_part
    
    def format_late_time(minutes):
        hours = minutes // 60
        mins = minutes % 60

        if hours > 0:
            return f"{hours} hr {mins} min"
        else:
            return f"{mins} min"

    @app.before_request
    def run_warning_letter_generator():
        active = get_active_user()

        if active and active["role"] == "admin":
            generate_weekly_warning_letters()
    
    @app.before_request
    def session_timeout():

        active_user = get_active_user()

        if not active_user:
            return

        now = datetime.now()

        if "last_activity" in session:

            last_activity = datetime.fromisoformat(
                session["last_activity"]
            )

            if now - last_activity > timedelta(minutes=15):

                session.clear()

                flash(
                    "Your session has expired due to inactivity.",
                    "warning"
                )

                return redirect(url_for("login"))

        session["last_activity"] = now.isoformat()
    
    @app.template_filter('format_date')
    def format_date_filter(dt):
        return format_date_with_suffix(dt)


    @app.template_filter('format_datetime')
    def format_datetime_filter(dt):
        return format_datetime(dt)
    
    @app.context_processor
    def inject_notification_count():

        conn = None
        cur = None

        try:

            active_user = get_active_user()

            if not active_user:
                return {
                    "unread_count": 0
                }

            conn = get_db()

            cur = conn.cursor(
                pymysql.cursors.DictCursor
            )

            unread_count = get_unread_notification_count(
                cur,
                active_user["user_id"]
            )

            return {
                "unread_count": unread_count
            }

        except Exception as e:

            print("NOTIFICATION COUNT ERROR:", e)

            return {
                "unread_count": 0
            }

        finally:

            if cur:
                cur.close()

    @app.after_request
    def add_header(response):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, proxy-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        response.headers["Surrogate-Control"] = "no-store"
        return response

    # ==================================================
    # INDEX
    # ==================================================
    @app.route("/")
    def index():
        return render_template("index.html")

    # ==================================================
    # LOGIN
    # ==================================================
    @app.route("/login", methods=["GET", "POST"])
    def login():
        error = None

        if request.method == "POST":

            captcha_response = request.form.get("g-recaptcha-response")

            secret_key = "6LdZ6PQsAAAAAPKf_lW76g-6R7gOyX3W5qNmI_NJ"

            verify_url = "https://www.google.com/recaptcha/api/siteverify"

            data = {
                "secret": secret_key,
                "response": captcha_response
            }

            r = requests.post(verify_url, data=data)
            result = r.json()

            if not result["success"]:
                return render_template(
                    "login.html",
                    error="Please complete CAPTCHA"
                )
            
            email = request.form.get("email", "").strip()
            password = request.form.get("password", "").strip()

            conn = get_db()
            cur = conn.cursor(pymysql.cursors.DictCursor)

            cur.execute("SELECT * FROM users WHERE email=%s", (email,))
            user = cur.fetchone()
                
            # =========================================
            # INVALID LOGIN
            # =========================================

            if not user or not check_password_hash(user["password"], password):

                # =========================================
                # LOG FAILED ATTEMPT
                # =========================================

                if user:

                    cur.execute("""
                        INSERT INTO login_attempts (
                            user_id,
                            ip_address,
                            status
                        )
                        VALUES (%s, %s, %s)
                    """, (
                        user["user_id"],
                        request.remote_addr,
                        "failed"
                    ))

                    conn.commit()

                error = "Invalid email or password"

                return render_template(
                    "login.html",
                    error=error
                )

            # =========================================
            # LOG SUCCESS LOGIN
            # =========================================

            cur.execute("""
                INSERT INTO login_attempts (
                    user_id,
                    ip_address,
                    status
                )
                VALUES (%s, %s, %s)
            """, (
                user["user_id"],
                request.remote_addr,
                "success"
            ))

            conn.commit()

            role = user["role"]

            session[f"{role}_user_id"] = user["user_id"]
            session[f"{role}_name"] = user["name"]

            session["active_role"] = role

            session["last_activity"] = datetime.now().isoformat()

            # =========================================
            # SECURE SESSION
            # =========================================

            session.permanent = True

            # SHOW CURFEW POPUP AFTER LOGIN
            if role == "student":
                session["show_curfew_popup"] = True
                session["show_urgent_popup"] = True
                            
            # FORCE PASSWORD CHANGE
            if user.get("force_password_change") == 1:
                return redirect(url_for("update_password_forced"))

            cur.close()

            return redirect(url_for(f"{user['role']}_dashboard"))

        return render_template("login.html", error=error)

    @app.route("/update-password/forced", methods=["GET", "POST"])
    @login_required()
    def update_password_forced():
        error = None

        if request.method == "POST":
            new_password = request.form.get("new_password")
            confirm_password = request.form.get("confirm_password")

            if new_password != confirm_password:
                error = "Passwords do not match."

            elif not validate_password(new_password):
                error = (
                    "Password must be at least 8 characters and include "
                    "uppercase, lowercase, number, and special character."
                )

            else:
                hashed_pw = generate_password_hash(new_password)

                conn = get_db()
                cur = conn.cursor()
                cur.execute("""
                    UPDATE users
                    SET password=%s, force_password_change=0
                    WHERE user_id=%s
                """, (hashed_pw, get_active_user()["user_id"]))
                conn.commit()
                cur.close()

                # =========================
                # SHOW PROFILE REMINDER
                # FOR STUDENTS ONLY
                # =========================
                if get_active_user()["role"] == "student":

                    session["show_profile_reminder"] = True

                    return redirect(url_for("student_dashboard"))

                # =========================
                # SECURITY OFFICER
                # =========================
                elif get_active_user()["role"] == "security":

                    return redirect(url_for("security_dashboard"))

                # =========================
                # ADMIN
                # =========================
                else:

                    return redirect(url_for("admin_dashboard"))

        return render_template(
            "update_password_forced.html",
            mode="forced",
            error=error
        )

    @app.route("/forgot-password", methods=["GET", "POST"])
    def forgot_password():
        error = None
        success = None

        if request.method == "GET":
                session.pop("reset_step", None)
                session.pop("reset_otp", None)
                session.pop("reset_email", None)
                step = "email"
        else:
            step = session.get("reset_step", "email")

        if request.method == "POST":

            # STEP 1: REQUEST OTP
            if step == "email":
                # =========================================
                # CAPTCHA VALIDATION
                # =========================================

                captcha_response = request.form.get("g-recaptcha-response")

                secret_key = "6LdZ6PQsAAAAAPKf_lW76g-6R7gOyX3W5qNmI_NJ"

                verify_url = "https://www.google.com/recaptcha/api/siteverify"

                data = {
                    "secret": secret_key,
                    "response": captcha_response
                }

                r = requests.post(verify_url, data=data)

                result = r.json()

                if not result["success"]:

                    error = "Please complete CAPTCHA"

                    return render_template(
                        "forgot_password.html",
                        step="email",
                        error=error
                    )

                email = request.form.get("email")

                conn = get_db()
                cur = conn.cursor(pymysql.cursors.DictCursor)
                cur.execute("SELECT user_id FROM users WHERE email=%s", (email,))
                user = cur.fetchone()
                cur.close()

                if not user:
                    error = "Email address not found."
                else:
                    otp = ''.join(random.choices(string.digits, k=6))
                    session["reset_otp"] = otp
                    session["reset_email"] = email
                    session["reset_step"] = "verify"

                    send_otp_email(email, otp)

                    print("DEBUG EMAIL_USER:", os.getenv("EMAIL_USER"))
                    print("DEBUG EMAIL_PASS exists:", os.getenv("EMAIL_PASS") is not None)

                    success = "OTP has been sent to your email."
                    step = "verify"

            # STEP 2: VERIFY OTP
            elif step == "verify":
                entered_otp = request.form.get("otp")

                if entered_otp != session.get("reset_otp"):
                    error = "Invalid OTP."
                else:
                    session["reset_step"] = "reset"
                    step = "reset"   # ⭐ REQUIRED

            # STEP 3: RESET PASSWORD
            elif step == "reset":
                new_password = request.form.get("new_password")
                confirm_password = request.form.get("confirm_password")

                if new_password != confirm_password:
                    error = "Passwords do not match."

                elif not validate_password(new_password):
                    error = (
                        "Password must be at least 8 characters and include "
                        "uppercase, lowercase, number, and special character."
                    )

                else:
                    hashed = generate_password_hash(new_password)

                    conn = get_db()
                    cur = conn.cursor()
                    cur.execute("""
                        UPDATE users
                        SET password=%s, force_password_change=0
                        WHERE email=%s
                    """, (hashed, session["reset_email"]))
                    conn.commit()
                    cur.close()

                    # CLEAN SESSION
                    session.pop("reset_otp", None)
                    session.pop("reset_email", None)
                    session.pop("reset_step", None)

                    return redirect(url_for("login"))

        return render_template(
            "forgot_password.html",
            step=step,
            error=error,
            success=success,
            email=session.get("reset_email")
        )

    # ==================================================
    # LOGOUT
    # ==================================================
    @app.route("/logout/<role>")
    def logout(role):

        session.pop(f"{role}_user_id", None)
        session.pop(f"{role}_name", None)

        active = get_active_user()

        if active and active["role"] == role:
            session.pop("active_role", None)

        return redirect(url_for("login"))

    # ==================================================
    # UPDATE PASSWORD (ALL ROLES)
    # ==================================================
    @app.route("/update-password", methods=["GET", "POST"])
    @login_required()
    def update_password():
        error = None

        if request.method == "POST":
            new_password = request.form.get("new_password")
            confirm_password = request.form.get("confirm_password")

            if new_password != confirm_password:
                error = "Passwords do not match."

            elif not validate_password(new_password):
                error = (
                    "Password must be at least 8 characters and include "
                    "uppercase, lowercase, number, and special character."
                )

            else:
                hashed = generate_password_hash(new_password)

                conn = get_db()
                cur = conn.cursor()

                # Update password ONLY
                cur.execute("""
                    UPDATE users
                    SET password=%s
                    WHERE user_id=%s
                """, (hashed, get_active_user()["user_id"]))

                conn.commit()
                cur.close()

                return redirect(url_for(f"{get_active_user()['role']}_dashboard"))

        return render_template(
            "update_password.html",
            error=error
        )

    # ==================================================
    # ADMIN DASHBOARD
    # ==================================================
    @app.route("/admin/dashboard")
    @login_required(role="admin")
    def admin_dashboard():
        conn = get_db()

        cur_user = conn.cursor(pymysql.cursors.DictCursor)

        cur_user.execute("""
            SELECT user_id, name, role
            FROM users
            WHERE user_id = %s
        """, (session.get("admin_user_id"),))

        active_user = cur_user.fetchone()

        cur_user.close()

        stats = {
            "pending_violations": 0,
            "pending_excuse_letters": 0,
            "pending_warning_letters": 0,
            "notification_count": 0
        }

        activity_logs = []
        notifications = []
        monthly_labels = []
        monthly_values = []

        if conn:
            cur = conn.cursor(pymysql.cursors.DictCursor)

            try:
                # Pending unexcused violations
                cur.execute("""
                    SELECT COUNT(*) AS count
                    FROM violations
                    WHERE status = 'Unexcused'
                """)

                stats["pending_violations"] = cur.fetchone()["count"]

                # Pending excuse letters
                cur.execute("""
                    SELECT COUNT(*) AS count
                    FROM appeals
                    WHERE status = 'Pending'
                """)

                stats["pending_excuse_letters"] = cur.fetchone()["count"]

                # Pending warning letters
                cur.execute("""
                    SELECT COUNT(*) AS count
                    FROM warning_letters
                    WHERE warning_letter_status = 'Draft'
                """)

                stats["pending_warning_letters"] = cur.fetchone()["count"]

                # Notification unread count
                stats["notification_count"] = get_unread_notification_count(cur, get_current_user("admin")["user_id"])

                # Latest notifications
                notifications = get_latest_notifications(cur, get_active_user()["user_id"], 4)

                # Activity logs 
                cur.execute(""" 
                    SELECT 
                    s.student_name,
                    s.matric_no AS matric_number, 
                    s.block, 
                    cir.detection_method AS method, 
                    cir.detected_time AS timestamp, 
                    v.status
                    FROM violations v 
                    JOIN check_in_records cir ON v.checkin_id = cir.checkin_id 
                    JOIN students s ON cir.user_id = s.user_id 
                    ORDER BY cir.detected_time DESC LIMIT 3 
                """) 
                
                activity_logs = cur.fetchall()

                # Monthly Curfew Violation Trend
                monthly_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

                monthly_values = [0] * 12

                cur.execute("""
                    SELECT
                        MONTH(violation_date) AS month_num,
                        COUNT(*) AS total
                    FROM violations
                    WHERE YEAR(violation_date) = YEAR(CURDATE())
                    GROUP BY MONTH(violation_date)
                """)

                monthly_data = cur.fetchall()

                for row in monthly_data:
                    monthly_values[row["month_num"] - 1] = row["total"]

            finally:
                cur.close()

        return render_template(
            "dash_admin.html",
            stats=stats,
            activity_logs=activity_logs,
            notifications=notifications,
            monthly_labels=monthly_labels,
            monthly_values=monthly_values,
            active_user=active_user
        )

    @app.route("/admin/profile/update", methods=["POST"])
    @login_required(role="admin")
    def update_admin_profile():

        conn = get_db()
        cur = conn.cursor()

        user_id = get_current_user("admin")["user_id"]

        name = request.form.get("name")
        email = request.form.get("email")
        phone = request.form.get("phone")
        position = request.form.get("position")

        # UPDATE USERS TABLE
        cur.execute("""
            UPDATE users
            SET name=%s,
                email=%s
            WHERE user_id=%s
        """, (name, email, user_id))

        # UPDATE ADMINS TABLE
        cur.execute("""
            UPDATE admins
            SET admin_phone=%s,
                position=%s
            WHERE user_id=%s
        """, (phone, position, user_id))

        # PROFILE PICTURE
        profile_pic = request.files.get("profile_pic")

        if profile_pic and profile_pic.filename != "":

            filename = secure_filename(profile_pic.filename)

            upload_path = os.path.join(
                app.root_path,
                "static/images/profiles",
                filename
            )

            profile_pic.save(upload_path)

            db_path = f"images/profiles/{filename}"

            cur.execute("""
                UPDATE admins
                SET admin_official_pic=%s
                WHERE user_id=%s
            """, (db_path, user_id))

        conn.commit()

        cur.close()

        flash("Profile updated successfully!", "success")

        return redirect(url_for("admin_profile"))

    @app.route("/admin/profile", methods=["GET", "POST"])
    @login_required(role="admin")
    def admin_profile():
        conn = get_db()
        cur = conn.cursor(pymysql.cursors.DictCursor)

        cur.execute("""
            SELECT u.name,
                u.email,
                u.created_at,
                a.admin_official_pic,
                a.admin_id,
                a.position,
                a.admin_phone
            FROM users u
            JOIN admins a ON u.user_id = a.user_id
            WHERE u.user_id=%s
        """, (get_current_user("admin")["user_id"],))
        admin_data = cur.fetchone()
        cur.close()

        return render_template("admin_profile.html", admin_data=admin_data)

    @app.route("/admin/students")
    @login_required(role="admin")
    def admin_list_students():

        conn = get_db()
        cur = conn.cursor(pymysql.cursors.DictCursor)

        # STUDENTS
        cur.execute("""
            SELECT *, student_official_pic
            FROM students
        """)
        students = cur.fetchall()

        # SECURITY COUNT
        cur.execute("SELECT COUNT(*) AS total FROM security_officers")
        security_count = cur.fetchone()["total"]

        # ADMIN COUNT
        cur.execute("SELECT COUNT(*) AS total FROM admins")
        admin_count = cur.fetchone()["total"]

        cur.close()

        return render_template(
            "admin_list_students.html",
            students=students,
            security_count=security_count,
            admin_count=admin_count
        )

    @app.route('/import_students', methods=['POST'])
    def import_students():

        file = request.files['excel_file']

        if not file:
            flash('No file selected')
            return redirect(url_for('students'))

        df = pd.read_excel(file)

        conn = get_db()
        cur = conn.cursor()

        for _, row in df.iterrows():

            # Check duplicate email
            cur.execute(
                "SELECT user_id FROM users WHERE email=%s",
                (row["student_email"],)
            )

            if cur.fetchone():
                continue

            # 1. Create user account
            cur.execute("""
                INSERT INTO users
                (
                    email,
                    password,
                    name,
                    role,
                    force_password_change
                )
                VALUES (%s,%s,%s,'student',1)
            """, (
                row["student_email"],
                generate_password_hash("student123"),
                row["student_name"]
            ))

            user_id = cur.lastrowid

            # 2. Create student profile
            cur.execute("""
                INSERT INTO students
                (
                    user_id,
                    student_name,
                    student_ic_no,
                    matric_no,
                    student_email,
                    student_phone,
                    block,
                    room_no,
                    faculty,
                    course,
                    profile_completed
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                user_id,
                row["student_name"],
                row["student_ic_no"],
                row["matric_no"],
                row["student_email"],
                row["student_phone"],
                row["block"],
                row["room_no"],
                row["faculty"],
                row["course"],
                0
            ))

        conn.commit()

        cur.close()

        flash('Students imported successfully')

        return redirect(url_for('students'))

    @app.route("/admin/students/add", methods=["POST"])
    @login_required(role="admin")
    def admin_add_students():
        conn = get_db()
        cur = conn.cursor()

        try:
            # ==========================
            # 📧 CHECK DUPLICATE EMAIL
            # ==========================
            cur.execute("SELECT user_id FROM users WHERE email=%s",
                        (request.form["student_email"],))

            if cur.fetchone():
                flash("Email already exists.", "danger")
                return redirect(url_for("admin_list_students"))
        
            # 1️⃣ CREATE USER (LOGIN ACCOUNT)
            cur.execute("""
            INSERT INTO users (email, password, name, role, force_password_change)
            VALUES (%s, %s, %s, 'student', 1)
            """, (
                request.form["student_email"],
                generate_password_hash("student123"),
                request.form["student_name"]
            ))

            # 2️⃣ GET AUTO-GENERATED user_id
            user_id = cur.lastrowid

            # 3️⃣ CREATE STUDENT PROFILE
            cur.execute("""
                INSERT INTO students (
                    user_id,
                    student_name,
                    student_ic_no,
                    matric_no,
                    student_email,
                    student_phone,
                    block,
                    room_no,
                    faculty,
                    course,
                    profile_completed
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                user_id,
                request.form["student_name"],
                request.form["student_ic_no"],
                request.form["matric_no"],
                request.form["student_email"],
                request.form["student_phone"],
                request.form["block"],
                request.form["room_no"],
                request.form["faculty"],
                request.form["course"],
                0
            ))

            notify_role(
                cur,
                "admin",
                "New User Created",
                "A new user account has been created.",
                "user"
            )

            conn.commit()
            flash("Student added successfully! Default password: student123", "success")

        except Exception as e:
            conn.rollback()
            print("❌ ADD STUDENT ERROR:", e)
            flash(f"Error: {str(e)}", "danger")

        finally:
            cur.close()

        return redirect(url_for("admin_list_students"))
    
    @app.route("/admin/students/delete/<int:user_id>", methods=["POST"])
    @login_required(role="admin")
    def admin_delete_student(user_id):
        conn = get_db()
        cur = conn.cursor()

        try:
            # DELETE USER → CASCADE deletes student profile
            cur.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
            conn.commit()

            flash("Student deleted successfully.", "success")

        except Exception as e:
            conn.rollback()
            print("❌ DELETE STUDENT ERROR:", e)
            flash("Failed to delete student.", "danger")

        finally:
            cur.close()

        return redirect(url_for("admin_list_students"))
    
    @app.route("/admin/students/export")
    @login_required(role="admin")
    def export_students():
        conn = get_db()
        cur = conn.cursor(pymysql.cursors.DictCursor)

        cur.execute("""
            SELECT student_name,
                matric_no,
                faculty,
                block,
                room_no,
                student_email,
                student_phone
            FROM students
        """)

        students = cur.fetchall()
        cur.close()

        si = StringIO()
        writer = csv.writer(si)

        writer.writerow([
            "Name", "Matric Number", "Faculty",
            "Block", "Room", "Email", "Phone"
        ])

        for s in students:
            writer.writerow([
                s["student_name"],
                s["matric_no"],
                s["faculty"],
                s["block"],
                f'="{s["room_no"]}"',
                s["student_email"],
                f'="{s["student_phone"]}"'
            ])

        return Response(
            si.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition":
                    "attachment;filename=student_list.csv"}
        )

    @app.route("/admin/security")
    @login_required(role="admin")
    def admin_list_security():

        conn = get_db()
        cur = conn.cursor(pymysql.cursors.DictCursor)

        # SECURITY LIST
        cur.execute("SELECT * FROM security_officers")
        security_officers = cur.fetchall()

        # STUDENT COUNT
        cur.execute("SELECT COUNT(*) AS total FROM students")
        student_count = cur.fetchone()["total"]

        # ADMIN COUNT
        cur.execute("SELECT COUNT(*) AS total FROM admins")
        admin_count = cur.fetchone()["total"]

        cur.close()

        return render_template(
            "admin_list_security.html",
            security_officers=security_officers,
            students=[None] * student_count,
            security_count=len(security_officers),
            admin_count=admin_count
        )
    
    @app.route("/admin/security/add", methods=["POST"])
    @login_required(role="admin")
    def admin_add_security():
        conn = get_db()
        cur = conn.cursor()

        try:
            # 1️⃣ CREATE USER LOGIN
            cur.execute("""
                INSERT INTO users (email, role, password, force_password_change)
                VALUES (%s, 'security', %s, 0)
            """, (
                request.form["officer_email"],
                generate_password_hash("officer123")
            ))

            # get generated user_id
            user_id = cur.lastrowid

            # 2️⃣ CREATE SECURITY OFFICER PROFILE
            cur.execute("""
                INSERT INTO security_officers (
                    user_id,
                    staff_id,
                    officer_name,
                    officer_email,
                    officer_phone
                ) VALUES (%s,%s,%s,%s,%s,)
            """, (
                user_id,
                request.form["staff_id"],
                request.form["officer_name"],
                request.form["officer_email"],
                request.form["officer_phone"]
            ))

            notify_role(
                cur,
                "admin",
                "New User Created",
                "A new user account has been created.",
                "user"
            )

            conn.commit()
            flash("Security officer added successfully! Default password: officer123", "success")

        except Exception as e:
            conn.rollback()
            print("❌ ADD SECURITY OFFICER ERROR:", e)
            flash("Failed to add officer. Email or Staff ID may already exist.", "danger")

        finally:
            cur.close()

        return redirect(url_for("admin_list_security"))
    
    @app.route("/admin/security/delete/<int:user_id>", methods=["POST"])
    @login_required(role="admin")
    def admin_delete_security(user_id):
        conn = get_db()
        cur = conn.cursor()

        try:
            # DELETE USER → CASCADE deletes security_officers
            cur.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
            conn.commit()
            flash("Security officer deleted successfully.", "success")

        except Exception as e:
            conn.rollback()
            print("❌ DELETE SECURITY OFFICER ERROR:", e)
            flash("Failed to delete security officer.", "danger")

        finally:
            cur.close()

        return redirect(url_for("admin_list_security"))

    @app.route("/admin/admins")
    @login_required(role="admin")
    def admin_list_admins():

        conn = get_db()
        cur = conn.cursor(pymysql.cursors.DictCursor)

        # ADMINS
        cur.execute("SELECT * FROM admins")
        admins = cur.fetchall()

        # STUDENT COUNT
        cur.execute("SELECT COUNT(*) AS total FROM students")
        student_count = cur.fetchone()["total"]

        # SECURITY COUNT
        cur.execute("SELECT COUNT(*) AS total FROM security_officers")
        security_count = cur.fetchone()["total"]

        cur.close()

        return render_template(
            "admin_list_admins.html",
            admins=admins,
            students=[None] * student_count,
            security_count=security_count,
            admin_count=len(admins)
        )

    @app.route("/admin/admins/add", methods=["POST"])
    @login_required(role="admin")
    def admin_add_admin():
        conn = get_db()
        cur = conn.cursor()

        try:
            # CHECK IF EMAIL EXISTS
            cur.execute("SELECT * FROM users WHERE email=%s", (request.form["admin_email"],))
            existing = cur.fetchone()

            if existing:
                flash("Email already exists in the system.", "danger")
                return redirect(url_for("admin_list_admins"))
            
            # 1️⃣ CREATE LOGIN ACCOUNT
            cur.execute("""
                INSERT INTO users (email, role, password, force_password_change)
                VALUES (%s, 'admin', %s, 0)
            """, (
                request.form["admin_email"],
                generate_password_hash("admin123")
            ))

            user_id = cur.lastrowid

            # 2️⃣ CREATE ADMIN PROFILE
            cur.execute("""
                INSERT INTO admins (
                    user_id,
                    position,
                    admin_id,
                    admin_name,
                    admin_email,
                    admin_phone
                ) VALUES (%s,%s,%s,%s,%s,%s)
            """, (
                user_id,
                request.form["position"],
                request.form["admin_id"],
                request.form["admin_name"],
                request.form["admin_email"],
                request.form["admin_phone"]
            ))

            notify_role(
                cur,
                "admin",
                "New User Created",
                "A new user account has been created.",
                "user"
            )

            conn.commit()
            flash("Admin added successfully! Default password: admin123", "success")

        except Exception as e:
            conn.rollback()
            print("❌ ADD ADMIN ERROR:", e)
            flash("Failed to add admin. Email or Admin ID may already exist.", "danger")

        finally:
            cur.close()

        return redirect(url_for("admin_list_admins"))
    
    @app.route("/admin/admins/delete/<int:user_id>", methods=["POST"])
    @login_required(role="admin")
    def admin_delete_admin(user_id):
        conn = get_db()
        cur = conn.cursor()

        try:
            # CASCADE deletes admin profile automatically
            cur.execute("DELETE FROM users WHERE user_id=%s", (user_id,))
            conn.commit()
            flash("Admin deleted successfully.", "success")

        except Exception as e:
            conn.rollback()
            print("❌ DELETE ADMIN ERROR:", e)
            flash("Failed to delete admin.", "danger")

        finally:
            cur.close()

        return redirect(url_for("admin_list_admins"))

    @app.route("/admin/violations")
    @login_required(role="admin")
    def admin_violations():
        conn = get_db()
        cur = conn.cursor(pymysql.cursors.DictCursor)
        cur.execute("""
            SELECT
                v.*,

                s.student_name,
                s.matric_no,
                s.student_email,
                s.student_phone,
                s.student_ic_no,
                s.faculty,
                s.course,
                s.block,
                s.room_no,
                s.student_official_pic,

                cir.detection_method,

                a.appeal_id,
                a.reason AS appeal_reason,
                a.status AS appeal_status,
                a.admin_comment,
                a.appeal_file_path,
                a.submitted_at,

                wl.warning_id,
                wl.warning_letter_status,
                wl.reason,
                wl.file_path AS warning_file,
                wl.acknowledged_at

            FROM violations v

            JOIN students s
                ON v.user_id = s.user_id

            LEFT JOIN check_in_records cir
                ON v.checkin_id = cir.checkin_id

            LEFT JOIN appeals a
                ON v.violation_id = a.violation_id

            LEFT JOIN warning_letters wl
                ON wl.violation_id = v.violation_id

            ORDER BY v.violation_date DESC
        """)
        violations = cur.fetchall()
        cur.close()
        return render_template(
            "admin_violations.html", 
            violations=violations
        )
    
    @app.route("/admin/encrypt-face-templates")
    def encrypt_face_templates():

        conn = get_db()
        cur = conn.cursor(
            pymysql.cursors.DictCursor
        )

        cur.execute("""
            SELECT
                template_id,
                embedding_data
            FROM face_templates
        """)

        rows = cur.fetchall()

        for row in rows:

            try:

                json.loads(
                    row["embedding_data"]
                )

                encrypted = encrypt_embedding(
                    row["embedding_data"]
                )

                cur.execute("""
                    UPDATE face_templates
                    SET embedding_data = %s
                    WHERE template_id = %s
                """, (
                    encrypted,
                    row["template_id"]
                ))

            except:
                pass

        conn.commit()

        cur.close()

        return "All embeddings encrypted successfully."

    @app.route("/admin/excuse-letters")
    @login_required(role="admin")
    def admin_excuse_letter():
        conn = get_db()
        cur = conn.cursor(pymysql.cursors.DictCursor)

        try:
            cur.execute("""
                SELECT
                    a.*,
                    s.student_name,
                    s.matric_no,
                    s.student_email,
                    s.block,
                    s.room_no,
                    v.violation_date,
                    v.status AS violation_status,
                    v.late_minutes,
                    v.remarks, 
                    
                    DATE_FORMAT(
                        a.reviewed_at,
                        '%d %M %Y %h.%i%p'
                    ) AS formatted_reviewed_at
                        
                FROM appeals a
                JOIN students s
                    ON a.user_id = s.user_id
                LEFT JOIN violations v
                    ON a.violation_id = v.violation_id
                ORDER BY violation_date DESC
            """)
            appeals = cur.fetchall()

            return render_template("admin_excuse_letter.html", appeals=appeals)

        finally:
            cur.close()

    @app.route("/admin/appeal-file/<int:appeal_id>")
    @login_required(role="admin")
    def admin_appeal_file(appeal_id):
        conn = get_db()
        cur = conn.cursor(pymysql.cursors.DictCursor)

        try:
            cur.execute("""
                SELECT appeal_file_path
                FROM appeals
                WHERE appeal_id = %s
            """, (appeal_id,))
            appeal = cur.fetchone()

            if not appeal or not appeal.get("appeal_file_path"):
                abort(404)

            stored_path = appeal["appeal_file_path"].strip().replace("\\", "/")
            file_abs_path = os.path.join(app.root_path, "static", stored_path)

            if not os.path.exists(file_abs_path):
                abort(404)

            return send_file(file_abs_path, as_attachment=False)

        finally:
            cur.close()
    
    @app.route("/admin/review-appeal", methods=["POST"])
    @login_required(role="admin")
    def admin_review_appeal():
        conn = get_db()
        cur = conn.cursor(pymysql.cursors.DictCursor)

        try:
            appeal_id = request.form.get("appeal_id")
            decision = request.form.get("decision")
            admin_comment = request.form.get("admin_comment", "").strip()
            admin_signature = request.form.get("admin_signature", "").strip()

            if not appeal_id or decision not in ["Approved", "Unexcused"]:
                flash("Invalid review request.", "danger")
                return redirect(url_for("admin_excuse_letter"))

            if not admin_signature:
                flash("Please provide digital signature before approving.", "danger")
                return redirect(url_for("admin_excuse_letter"))

            cur.execute("""
                SELECT appeal_id, user_id, violation_id, submission_type
                FROM appeals
                WHERE appeal_id = %s
            """, (appeal_id,))
            appeal = cur.fetchone()

            if not appeal:
                flash("Appeal not found.", "danger")
                return redirect(url_for("admin_excuse_letter"))

            cur.execute("""
                UPDATE appeals
                SET status = %s,
                    admin_comment = %s,
                    admin_signature = %s,
                    reviewed_by = %s,
                    reviewed_at = NOW()
                WHERE appeal_id = %s
            """, (
                decision,
                admin_comment if admin_comment else None,
                admin_signature if admin_signature else None,
                get_current_user("admin")["user_id"],
                appeal_id
            ))

            # Only violation-type submissions should update violations table
            if appeal["submission_type"] == "violation" and appeal["violation_id"]:
                if decision == "Approved":
                    cur.execute("""
                        UPDATE violations
                        SET status = 'Approved'
                        WHERE violation_id = %s
                    """, (appeal["violation_id"],))
                else:
                    cur.execute("""
                        UPDATE violations
                        SET status = 'Unexcused'
                        WHERE violation_id = %s
                    """, (appeal["violation_id"],))

            if decision == "Approved":
                title = "Excuse Letter Approved"
                message = "Your submission has been approved by the administrator."
            else:
                title = "Excuse Letter Rejected"
                message = "Your submission has been rejected by the administrator."

            notify_user(
                cur,
                appeal["user_id"],
                title,
                message,
                "appeal",
                related_appeal_id=appeal_id
            )

            conn.commit()
            flash(f"Submission {decision.lower()} successfully.", "success")
            return redirect(url_for("admin_excuse_letter"))

        finally:
            cur.close()

    @app.route("/admin/sign-letter/<letter_id>", methods=["POST"])
    @login_required(role="admin")
    def sign_letter(letter_id):
        try:
            data = request.get_json()

            if not data or "signature" not in data:
                return jsonify({"success": False, "error": "No signature received"}), 400

            signature = data.get("signature")
            admin_name = get_current_user("admin")["name"]

            conn = get_db()
            cur = conn.cursor()

            cur.execute("""
                UPDATE warning_letters
                SET 
                    admin_signature = %s,
                    warning_letter_status = 'Verified'
                WHERE warning_id = %s
            """, (signature, letter_id))

            conn.commit()
            cur.close()

            return jsonify({"success": True})

        except Exception as e:
            print("ERROR SIGNING LETTER:", e)
            return jsonify({"success": False}), 500

    @app.route("/admin/send-letter/<letter_id>", methods=["POST"])
    @login_required(role="admin")
    def send_letter(letter_id):
        conn = get_db()
        cur = conn.cursor(pymysql.cursors.DictCursor)

        cur.execute("""
            UPDATE warning_letters
            SET 
                warning_letter_status = 'Sent to Student'            
                WHERE warning_id = %s
        """, (letter_id,))

        # =========================================
        # GET LETTER + STUDENT INFO
        # =========================================
        cur.execute("""

            SELECT
                wl.warning_id,
                wl.user_id,
                v.violation_date,
                s.student_name,
                u.email

            FROM warning_letters wl

            JOIN students s
                ON wl.user_id = s.user_id

            JOIN users u
                ON wl.user_id = u.user_id

            LEFT JOIN violations v
                ON wl.violation_id = v.violation_id

            WHERE wl.warning_id = %s

        """, (letter_id,))
        
        letter = cur.fetchone()

        # =========================================
        # SEND SYSTEM NOTIFICATION
        # =========================================
        if letter:

            notify_user(
                cur,
                letter["user_id"],
                "Warning Letter Issued",
                "You have received a warning letter. Please review and acknowledge.",
                "warning_letter"
            )

            # =========================================
            # SEND EMAIL
            # =========================================
            violation_date = (
                letter["violation_date"].strftime("%d %B %Y")
                if letter["violation_date"]
                else "-"
            )

            send_warning_letter_email(
                letter["email"],
                letter["student_name"],
                f"WL{int(letter['warning_id']):03d}",
                violation_date
            )

        conn.commit()
        cur.close()

        return jsonify({"success": True})
    
    @app.route("/admin/download-warning-letter/<int:warning_id>")
    @login_required(role="admin")
    def download_warning_letter(warning_id):
        conn = get_db()
        cur = conn.cursor(pymysql.cursors.DictCursor)

        cur.execute("""
            SELECT 
                wl.*,
                s.student_name,
                s.matric_no,
                CONCAT(s.block, '-', s.room_no) AS block_room,

                v.violation_date,

                (
                    SELECT DATE_FORMAT(v.created_at, '%%h:%%i %%p')
                    FROM violations v
                    WHERE v.user_id = wl.user_id
                    ORDER BY v.created_at DESC
                    LIMIT 1
                ) AS violation_time

            FROM warning_letters wl

            JOIN students s
                ON wl.user_id = s.user_id
                
            LEFT JOIN violations v
                ON wl.violation_id = v.violation_id

            WHERE wl.warning_id = %s
        """, (warning_id,))
        
        letter = cur.fetchone()

        from datetime import datetime

        if letter['violation_date'] and isinstance(letter['violation_date'], str):
            letter['violation_date'] = datetime.strptime(letter['violation_date'], "%Y-%m-%d")

        if letter['issued_at'] and isinstance(letter['issued_at'], str):
            letter['issued_at'] = datetime.strptime(letter['issued_at'], "%Y-%m-%d %H:%M:%S")

        if not letter:
            return "Letter not found", 404

        # ✅ Render your new PDF template
        html = render_template("warning_letter_pdf.html", letter=letter)

        # ✅ wkhtmltopdf config (IMPORTANT)
        config = pdfkit.configuration(
            wkhtmltopdf=r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
        )

        # ✅ Convert HTML → PDF
        pdf = pdfkit.from_string(
            html,
            False,
            configuration=config,
            options={
                'enable-local-file-access': '',
                'quiet': ''            }
        )

        # ✅ Send file to browser
        response = make_response(pdf)
        response.headers["Content-Type"] = "application/pdf"
        response.headers["Content-Disposition"] = f"attachment; filename=warning_letter_{warning_id}.pdf"

        return response

    @app.route("/admin/view-warning-letter/<int:warning_id>")
    @login_required(role="admin")
    def view_warning_letter(warning_id):

        conn = get_db()
        cur = conn.cursor(pymysql.cursors.DictCursor)

        cur.execute("""
            SELECT 
                wl.*,
                s.student_name,
                s.matric_no,
                CONCAT(s.block, '-', s.room_no) AS block_room,

                v.violation_date,

                (
                    SELECT DATE_FORMAT(v.created_at, '%%h:%%i %%p')
                    FROM violations v
                    WHERE v.user_id = wl.user_id
                    ORDER BY v.created_at DESC
                    LIMIT 1
                ) AS violation_time

            FROM warning_letters wl

            JOIN students s
                ON wl.user_id = s.user_id

            LEFT JOIN violations v
                ON wl.violation_id = v.violation_id

            WHERE wl.warning_id = %s
        """, (warning_id,))

        letter = cur.fetchone()

        # ✅ IMPORTANT
        if not letter:
            return "Letter not found", 404

        from datetime import datetime

        # ✅ SAFE datetime conversion
        if letter.get('violation_date') and isinstance(letter['violation_date'], str):
            letter['violation_date'] = datetime.strptime(
                letter['violation_date'],
                "%Y-%m-%d"
            )

        if letter.get('issued_at') and isinstance(letter['issued_at'], str):
            letter['issued_at'] = datetime.strptime(
                letter['issued_at'],
                "%Y-%m-%d %H:%M:%S"
            )

        html = render_template(
            "warning_letter_pdf.html",
            letter=letter
        )

        config = pdfkit.configuration(
            wkhtmltopdf=r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
        )

        pdf = pdfkit.from_string(
            html,
            False,
            configuration=config,
            options={
                'enable-local-file-access': '',
                'quiet': ''
            }
        )

        response = make_response(pdf)

        response.headers["Content-Type"] = "application/pdf"

        response.headers["Content-Disposition"] = \
            f"inline; filename=warning_letter_{warning_id}.pdf"

        return response
    
    @app.route("/admin/warning-letters")
    @login_required(role="admin")
    def admin_warning_letters():
        conn = get_db()
        cur = conn.cursor(pymysql.cursors.DictCursor)

        try:

            # =========================================
            # 🔥 FETCH ALL WARNING LETTERS
            # =========================================
            cur.execute("""
                SELECT 
                    wl.*,
                    s.student_name,
                    s.matric_no,

                    -- ✅ combine block + room
                    CONCAT(s.block, '-', s.room_no) AS block_room,

                    v.violation_date,
                    DATE_FORMAT(v.created_at, '%h:%i %p') AS violation_time

                FROM warning_letters wl

                JOIN students s ON wl.user_id = s.user_id

                LEFT JOIN violations v
                    ON wl.violation_id = v.violation_id

                ORDER BY violation_date DESC
            """)

            warning_letters = cur.fetchall()

            # =========================================
            # 🔥 COUNTS (for your dashboard cards)
            # =========================================
            total_letters = len(warning_letters)

            acknowledged_letters = len([
                w for w in warning_letters 
                if w["warning_letter_status"] == "Confirmed"
            ])

            pending_letters = len([
                w for w in warning_letters 
                if w["warning_letter_status"] == "Sent to Student"
            ])
            warned_students = len(set([w["user_id"] for w in warning_letters]))

            return render_template(
                "admin_warning_letters.html",
                warning_letters=warning_letters,
                total_letters=total_letters,
                acknowledged_letters=acknowledged_letters,
                pending_letters=pending_letters,
                warned_students=warned_students,
                format_date=format_date_with_suffix,
                format_datetime=format_datetime
            )

        finally:
            cur.close()
    
    @app.route("/admin/generate-fines")
    @login_required(role="admin")
    def generate_fines():

        conn = get_db()
        cur = conn.cursor(pymysql.cursors.DictCursor)

        try:

            # =========================================
            # GET STUDENTS WITH WARNING LETTERS
            # =========================================
            cur.execute("""

                SELECT 
                    user_id,
                    COUNT(*) AS total_warnings

                FROM warning_letters

                GROUP BY user_id

                HAVING COUNT(*) >= 3

            """)

            students = cur.fetchall()

            generated = 0

            for student in students:

                user_id = student["user_id"]
                total_warnings = student["total_warnings"]

                # =========================================
                # COUNT EXISTING FINES
                # =========================================
                cur.execute("""
                    SELECT COUNT(*) AS total_fines
                    FROM fines
                    WHERE user_id = %s
                """, (user_id,))

                fine_result = cur.fetchone()

                total_fines = fine_result["total_fines"]

                # =========================================
                # REQUIRED FINES
                # Every 3 warning letters = 1 fine
                # =========================================
                required_fines = total_warnings // 3

                # =========================================
                # GENERATE MISSING FINES
                # =========================================
                while total_fines < required_fines:

                    print("CREATING FINE FOR:", user_id)

                    cur.execute("""
                        INSERT INTO fines (
                            user_id,
                            amount,
                            reason,
                            payment_status
                        )
                        VALUES (%s, %s, %s, %s)
                    """, (
                        user_id,
                        100.00,
                        'Exceeded 3 warning letters',
                        'Unpaid'
                    ))

                    total_fines += 1
                    generated += 1

                # =========================================
                # NOTIFY STUDENT
                # =========================================
                if generated > 0:

                    notify_user(
                        cur,
                        user_id,
                        "Penalty Payment Issued",
                        "A disciplinary fine has been issued due to excessive warning letters.",
                        "urgent"
                    )

            conn.commit()

            flash(f"{generated} fines generated successfully.", "success")

            return redirect(url_for("admin_warning_letters"))

        except Exception as e:

            conn.rollback()

            print("GENERATE FINES ERROR:", e)

            flash("Failed to generate fines.", "danger")

            return redirect(url_for("admin_warning_letters"))

        finally:
            cur.close()

    @app.route("/admin/fines")
    @login_required(role="admin")
    def admin_fines():

        conn = get_db()
        cur = conn.cursor(pymysql.cursors.DictCursor)

        try:

            cur.execute("""
                SELECT
                    f.fine_id,
                    f.user_id,
                    f.amount,
                    f.reason,
                    f.payment_status,

                    DATE_FORMAT(
                        f.created_at,
                        '%d %b %Y • %h:%i %p'
                    ) AS created_at,

                    f.receipt_no,
                    f.paid_at,

                    s.student_name,
                    s.matric_no,
                    s.block,
                    s.room_no

                FROM fines f

                JOIN students s
                    ON f.user_id = s.user_id

                ORDER BY f.created_at DESC
            """)

            fines = cur.fetchall()

            return render_template(
                "admin_fines.html",
                fines=fines
            )

        finally:
            cur.close()

    @app.route("/admin/send-overdue-notification/<int:fine_id>",
           methods=["POST"])
    @login_required(role="admin")
    def send_overdue_notification(fine_id):

        conn = get_db()
        cur = conn.cursor(pymysql.cursors.DictCursor)

        try:

            # =========================================
            # GET FINE INFO
            # =========================================
            cur.execute("""
                SELECT
                    f.*,
                    s.user_id,
                    s.student_name
                FROM fines f
                JOIN students s
                    ON f.user_id = s.user_id
                WHERE f.fine_id = %s
            """, (fine_id,))

            fine = cur.fetchone()

            if not fine:
                flash("Fine record not found.", "danger")
                return redirect(url_for("admin_fines"))

            # =========================================
            # CREATE NOTIFICATION
            # =========================================
            message = (
                f"Warning: Your penalty payment of "
                f"RM {fine['amount']:.2f} is overdue. "
                f"Please make payment immediately "
                f"to avoid further disciplinary action."
            )

            notify_user(
                cur,
                fine["user_id"],
                "Overdue Penalty Payment",
                message,
                "urgent"
            )

            conn.commit()

            flash(
                "Overdue payment notification sent successfully.",
                "success"
            )

        except Exception as e:

            conn.rollback()

            print("OVERDUE NOTIFICATION ERROR:", e)

            flash(
                "Failed to send overdue notification.",
                "danger"
            )

        finally:
            cur.close()

        return redirect(url_for("admin_fines"))

    @app.route("/admin/notifications", endpoint="admin_notifications")
    @login_required(role="admin")
    def admin_notifications():
        conn = get_db()
        cur = conn.cursor(pymysql.cursors.DictCursor)

        try:
            cur.execute("""
                SELECT
                    notification_id,
                    title,
                    message,
                    type,
                    is_read,
                    read_at,
                    created_at,
                    related_violation_id,
                    related_appeal_id
                FROM system_notifications
                WHERE user_id = %s
                ORDER BY created_at DESC
            """, (get_current_user("admin")["user_id"],))
            notifications = cur.fetchall()

            unread_count = get_unread_notification_count(cur, get_current_user("admin")["user_id"])

            return render_template(
                "admin_notifications.html",
                notifications=notifications,
                unread_count=unread_count
            )
        finally:
            cur.close()
    
    @app.route("/admin/generate-violators-pdf")
    @login_required(role="admin")
    def generate_violators_pdf():

        conn = get_db()
        cur = conn.cursor(pymysql.cursors.DictCursor)

        try:

            # ==========================================
            # TOP VIOLATORS
            # ==========================================
            cur.execute("""

                SELECT 

                    s.student_name,
                    s.matric_no,
                    s.block,

                    COUNT(v.violation_id) AS total_violations,

                    SUM(
                        CASE
                            WHEN v.status = 'Approved'
                            THEN 1
                            ELSE 0
                        END
                    ) AS excused_count,

                    (
                        SELECT COUNT(*)
                        FROM warning_letters wl
                        WHERE wl.user_id = s.user_id
                    ) AS warning_letter_count,

                    MAX(v.violation_date) AS last_violation

                FROM violations v

                JOIN students s
                    ON v.user_id = s.user_id

                GROUP BY s.user_id

                ORDER BY total_violations DESC

            """)

            students = cur.fetchall()

            excel_data = []

            for s in students:

                if s["warning_letter_count"] >= 2:
                    risk_level = "High Risk"
                elif s["total_violations"] >= 3:
                    risk_level = "Medium Risk"
                else:
                    risk_level = "Low Risk"

                excel_data.append({
                    "Student Name": s["student_name"],
                    "Matric No": s["matric_no"],
                    "Block": s["block"],
                    "Total Violations": s["total_violations"],
                    "Excused": s["excused_count"],
                    "Warning Letters": s["warning_letter_count"],
                    "Last Violation": s["last_violation"],
                    "Risk Level": risk_level
                })

            df = pd.DataFrame(excel_data)

            output = BytesIO()

            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df.to_excel(
                    writer,
                    sheet_name="Violators Report",
                    index=False
                )

            output.seek(0)

            return send_file(
                output,
                as_attachment=True,
                download_name="violators_report.xlsx",
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        finally:
            cur.close()

    @app.route('/admin/reports')
    @login_required(role="admin")
    def admin_reports_analytics():

        # =========================
        # DATABASE CONNECTION
        # =========================
        conn = get_db()
        cur = conn.cursor(pymysql.cursors.DictCursor)

        # =========================
        # FILTERS
        # =========================
        days = request.args.get('days', '30')
        block = request.args.get('block', 'all')

        # =========================
        # DATE FILTER
        # =========================
        date_condition = ""

        if days == "7":

            date_condition = """
                AND v.violation_date >= DATE_SUB(NOW(), INTERVAL 7 DAY)
            """

        elif days == "30":

            date_condition = """
                AND v.violation_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)
            """

        elif days == "60":

            date_condition = """
                AND v.violation_date >= DATE_SUB(NOW(), INTERVAL 60 DAY)
            """

        elif days == "90":

            date_condition = """
                AND v.violation_date >= DATE_SUB(NOW(), INTERVAL 90 DAY)
            """

        # =========================
        # BLOCK FILTER
        # =========================
        block_condition = ""

        if block != "all":

            block_condition = f"""
                AND s.block = '{block}'
            """

        # ====================================================
        # TOTAL VIOLATIONS
        # ====================================================
        cur.execute(f"""
            SELECT COUNT(*) AS total

            FROM violations v

            JOIN students s
                ON v.user_id = s.user_id

            WHERE 1=1
            {date_condition}
            {block_condition}
        """)

        total_violations = cur.fetchone()['total']

        # ====================================================
        # EXCUSED VIOLATIONS
        # ====================================================
        cur.execute(f"""
            SELECT COUNT(*) AS total

            FROM violations v

            JOIN students s
                ON v.user_id = s.user_id

            WHERE v.status = 'Approved'

            {date_condition}
            {block_condition}
        """)

        excused_violations = cur.fetchone()['total']

        # ====================================================
        # WARNING LETTERS
        # ====================================================
        cur.execute(f"""
            SELECT COUNT(*) AS total

            FROM warning_letters wl

            JOIN students s
                ON wl.user_id = s.user_id

            WHERE 1=1

            {block_condition}
        """)

        warning_letters = cur.fetchone()['total']

        # ====================================================
        # MONTHLY VIOLATIONS CHART
        # ====================================================
        cur.execute(f"""
            SELECT
                YEAR(v.violation_date) AS year_num,
                    MONTH(v.violation_date) AS month_num,
                    DATE_FORMAT(MIN(v.violation_date), '%b %Y') AS month, 
                                       
                COUNT(*) AS total_violations,

                SUM(
                    CASE
                        WHEN v.status = 'Approved'
                        THEN 1
                        ELSE 0
                    END
                ) AS excused_violations,

                SUM(
                    CASE
                        WHEN v.status != 'Approved'
                        THEN 1
                        ELSE 0
                    END
                ) AS unexcused_violations,

                (
                    SELECT COUNT(*)
                    FROM warning_letters wl
                    WHERE MONTH(wl.issued_at) = MONTH(MIN(v.violation_date))
                    AND YEAR(wl.issued_at) = YEAR(MIN(v.violation_date))
                ) AS warning_letters

            FROM violations v

            JOIN students s
                ON v.user_id = s.user_id

            WHERE 1=1
            {date_condition}
            {block_condition}

            GROUP BY
                YEAR(v.violation_date),
                MONTH(v.violation_date)

            ORDER BY
                YEAR(v.violation_date),
                MONTH(v.violation_date)
        """)

        monthly_results = cur.fetchall()

        months = []

        monthly_totals = []
        monthly_excused = []
        monthly_unexcused = []
        monthly_warning_letters = []

        for row in monthly_results:

            months.append(row['month'])

            monthly_totals.append(
                row['total_violations']
            )

            monthly_excused.append(
                row['excused_violations']
            )

            monthly_unexcused.append(
                row['unexcused_violations']
            )

            monthly_warning_letters.append(
                row['warning_letters']
            )

        # ====================================================
        # WEEKDAY COMPARISON
        # ====================================================
        cur.execute(f"""
            SELECT 
                DAYNAME(v.violation_date) AS day,
                COUNT(*) AS total

            FROM violations v

            JOIN students s
                ON v.user_id = s.user_id

            WHERE 1=1
            {date_condition}
            {block_condition}

            GROUP BY 
                DAYOFWEEK(v.violation_date),
                DAYNAME(v.violation_date)

            ORDER BY 
                DAYOFWEEK(v.violation_date)
        """)

        weekday_results = cur.fetchall()

        weekday_labels = []
        weekday_totals = []

        for row in weekday_results:

            weekday_labels.append(row['day'])
            weekday_totals.append(row['total'])

        # ====================================================
        # TOP VIOLATORS
        # ====================================================
        cur.execute(f"""

            SELECT 

                s.user_id,
                s.student_name,
                s.matric_no,
                s.block,

                COUNT(v.violation_id) AS total_violations,

                SUM(
                    CASE
                        WHEN v.status = 'Approved'
                        THEN 1
                        ELSE 0
                    END
                ) AS excused_count,

                SUM(
                    CASE
                        WHEN v.status != 'Approved'
                        THEN 1
                        ELSE 0
                    END
                ) AS unexcused_count,

                (
                    SELECT COUNT(*)
                    FROM warning_letters wl
                    WHERE wl.user_id = s.user_id
                ) AS warning_letter_count

            FROM violations v

            JOIN students s
                ON v.user_id = s.user_id

            WHERE 1=1
            {date_condition}
            {block_condition}

            GROUP BY s.user_id

            ORDER BY total_violations DESC

            LIMIT 10

        """)

        top_violators = cur.fetchall()

        # =========================
        # CLOSE CONNECTION
        # =========================
        cur.close()

        # =========================
        # RENDER TEMPLATE
        # =========================
        return render_template(

            'admin_reports_analytics.html',

            # SUMMARY CARDS
            total_violations = total_violations,
            excused_violations = excused_violations,
            warning_letters = warning_letters,

            # MONTHLY CHART
            months = months,
            monthly_totals = monthly_totals,
            monthly_excused = monthly_excused,
            monthly_unexcused = monthly_unexcused,
            monthly_warning_letters = monthly_warning_letters,

            # WEEKDAY CHART
            weekday_labels = weekday_labels,
            weekday_totals = weekday_totals,

            # TABLE
            top_violators = top_violators,

            # FILTERS
            selected_days = days,
            selected_block = block
        )

    # ==================================================
    # SECURITY DASHBOARD
    # ==================================================
    @app.route('/security/dashboard')
    @login_required(role="security")
    def security_dashboard():
        conn = get_db()
        cur = conn.cursor(pymysql.cursors.DictCursor)

        try:
            cur.execute("""
                SELECT 

                    DATE_FORMAT(
                        v.violation_date,
                        '%d %b %Y'
                    ) AS violation_date,

                    DATE_FORMAT(
                        v.created_at,
                        '%h:%i %p'
                    ) AS violation_time,

                    v.status,

                    s.student_name,
                    s.matric_no

                FROM violations v

                JOIN students s
                    ON v.user_id = s.user_id

                ORDER BY v.created_at DESC

                LIMIT 5
            """)
            violations = cur.fetchall()

            notification_count = get_unread_notification_count(cur, get_current_user("security")["user_id"])

            return render_template(
                'dash_security.html',
                stats={
                    "total_inspections": 3,
                    "pending_letters": 2,
                    "repeat_offenders": 2,
                    "notification_count": notification_count
                },
                violations=violations
            )
        finally:
            cur.close()
    
    @app.route("/security/verify-face", methods=["POST"])
    @login_required(role="security")
    def security_verify_face():
        data = request.get_json()
        image_data = data.get("image")
        print("SERVER TIME:", datetime.now())
        
        if not image_data:
            return jsonify({
                "success": False,
                "status": "error",
                "message": "No image received"
            }), 400

        conn = None
        cur = None

        try:
            # =========================
            # Decode image
            # =========================
            header, encoded = image_data.split(",", 1)
            img_bytes = base64.b64decode(encoded)
            np_arr = np.frombuffer(img_bytes, np.uint8)
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

            if frame is None:
                return jsonify({
                    "success": False,
                    "status": "error",
                    "message": "Invalid image"
                }), 400

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # =========================
            # Detect face
            # =========================
            face_locations = face_recognition.face_locations(rgb_frame)

            if len(face_locations) == 0:
                return jsonify({
                    "success": False,
                    "status": "no_face",
                    "message": "No face detected"
                }), 400

            if len(face_locations) > 1:
                return jsonify({
                    "success": False,
                    "status": "multiple_faces",
                    "message": "Multiple faces detected"
                }), 400

            face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)
            if not face_encodings:
                return jsonify({
                    "success": False,
                    "status": "error",
                    "message": "Unable to encode face"
                }), 400

            current_encoding = face_encodings[0]

            conn = get_db()
            cur = conn.cursor(pymysql.cursors.DictCursor)

            # =========================
            # Get all enrolled student templates
            # =========================
            cur.execute("""
                SELECT ft.user_id, ft.embedding_data, s.student_name
                FROM face_templates ft
                JOIN students s ON ft.user_id = s.user_id
            """)
            templates = cur.fetchall()

            if not templates:
                return jsonify({
                    "success": False,
                    "status": "error",
                    "message": "No enrolled student face data found"
                }), 404

            # =========================
            # Find best match
            # =========================
            best_match = None
            best_distance = 999.0

            for row in templates:
                try:
                    decrypted_json = decrypt_embedding(
                        row["embedding_data"]
                    )

                    stored_embedding = np.array(
                        json.loads(
                            decrypted_json
                        ),
                        dtype=np.float64
                    )

                    distance = float(np.linalg.norm(stored_embedding - current_encoding))

                    if distance < best_distance:
                        best_distance = distance
                        best_match = row
                except Exception as e:
                    print("Template parse error:", e)
                    continue

            # =========================
            # Match threshold
            # =========================
            MATCH_THRESHOLD = 0.50

            # If face exists but not in DB = stranger
            if best_match is None or best_distance > MATCH_THRESHOLD:
                return jsonify({
                    "success": False,
                    "status": "stranger",
                    "message": "Stranger detected",
                    "confidence_score": round(best_distance, 4)
                }), 401

            recognized_student_id = int(best_match["user_id"])

            # =========================================
            # CHECK UNPAID FINES
            # =========================================

            cur.execute("""
                SELECT fine_id
                FROM fines
                WHERE user_id = %s
                AND payment_status = 'Unpaid'
            """, (recognized_student_id,))

            unpaid_fine = cur.fetchone()

            if unpaid_fine:

                return jsonify({
                    "success": False,
                    "status": "blocked",
                    "message": "Outstanding fine detected. Payment required before late check-in."
                }), 403

            cur.execute("""
                SELECT student_name, matric_no, block, room_no
                FROM students
                WHERE user_id = %s
            """, (recognized_student_id,))
            student_info = cur.fetchone()

            if not student_info:
                return jsonify({
                    "success": False,
                    "status": "error",
                    "message": "Student details not found"
                }), 

            # =========================
            # Save captured image
            # =========================
            scan_dir = os.path.join("static", "checkin_faces")
            os.makedirs(scan_dir, exist_ok=True)

            filename = f"checkin_{recognized_student_id}_{int(time.time())}.jpg"
            image_path = os.path.join(scan_dir, filename)
            cv2.imwrite(image_path, frame)

            db_image_path = f"static/checkin_faces/{filename}"

            # =========================
            # Determine lateness
            # =========================
            now = datetime.now()
            detected_time = now.strftime("%Y-%m-%d %H:%M:%S")

            if now.hour < 6:
                curfew_base_date = now - timedelta(days=1)
            else:
                curfew_base_date = now

            curfew_time = curfew_base_date.replace(hour=22, minute=0, second=0, microsecond=0)

            # Use actual detected timestamp date
            violation_date = datetime.now().date()

            late_minutes = 0
            is_late = now > curfew_time

            if is_late:
                late_minutes = int((now - curfew_time).total_seconds() // 60)

            detected_by = int(get_current_user("security")["user_id"])

            # =========================
            # Prevent duplicate check-in
            # =========================
            cur.execute("""
                SELECT checkin_id FROM check_in_records
                WHERE user_id = %s
                AND detected_time >= NOW() - INTERVAL 1 MINUTE
            """, (recognized_student_id,))

            recent = cur.fetchone()

            if recent:
                return jsonify({
                    "success": False,
                    "status": "duplicate",
                    "message": "Student already checked in recently"
                }), 400

            # =========================
            # Insert check-in record
            # =========================
            cur.execute("""
                INSERT INTO check_in_records (
                    user_id,
                    recognized_student_id,
                    detection_method,
                    confidence_score,
                    detection_status,
                    image_path,
                    detected_time,
                    detected_by
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                recognized_student_id,
                recognized_student_id,
                "face",
                round(best_distance, 4),
                "Matched",
                db_image_path,
                detected_time,
                detected_by
            ))

            checkin_id = cur.lastrowid

            # =========================
            # Insert violation if late
            # =========================
            violation_created = False
            violation_id = None

            if is_late:
                # =========================================
                # CHECK APPROVED PRE-APPROVAL
                # =========================================
            
                cur.execute("""
                    SELECT appeal_id, status
                    FROM appeals
                    WHERE user_id = %s
                    AND submission_type = 'pre_approval'
                    AND DATE(planned_return_date) = %s
                    ORDER BY submitted_at DESC
                    LIMIT 1
                """, (
                    recognized_student_id,
                    violation_date
                ))

                existing_appeal = cur.fetchone()

                appeal_status = None
                appeal_id = None

                if existing_appeal:
                    appeal_id = existing_appeal["appeal_id"]
                    appeal_status = existing_appeal["status"]

                # =========================================
                # DETERMINE VIOLATION STATUS
                # =========================================

                violation_status = "Unexcused"
                violation_remarks = "Late check-in detected by face recognition"

                if appeal_status == "Approved":
                    violation_status = "Approved"
                    violation_remarks = "Late check-in covered by approved pre-approval"

                elif appeal_status == "Pending":
                    violation_status = "Pending"
                    violation_remarks = "Waiting for admin review of pre-approval"

                # =========================================
                # INSERT VIOLATION
                # =========================================

                cur.execute("""
                    INSERT INTO violations (
                        user_id,
                        checkin_id,
                        late_minutes,
                        violation_date,
                        status,
                        remarks
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    recognized_student_id,
                    checkin_id,
                    late_minutes,
                    str(violation_date),
                    violation_status,
                    violation_remarks
                ))

                violation_id = cur.lastrowid
                violation_created = True

                # =========================================
                # CONNECT APPEAL TO VIOLATION
                # =========================================
                if appeal_id:

                    cur.execute("""
                        UPDATE appeals
                        SET violation_id = %s,
                            checkin_id = %s
                        WHERE appeal_id = %s
                    """, (
                        violation_id,
                        checkin_id,
                        appeal_id
                    ))
                
                # =========================
                # 🔔 NOTIFICATIONS
                # =========================

                late_text = format_late_time(late_minutes)

                # ADMIN
                notify_role(
                    cur,
                    "admin",
                    "Curfew Violation Alert",
                    f"Student {student_info['student_name']} ({student_info['matric_no']}) was detected after curfew. Late by {late_text}.",
                    "violation",
                    related_violation_id=violation_id
                )

                # SECURITY
                notify_role(
                    cur,
                    "security",
                    "Late Check-in Alert",
                    f"Student {student_info['student_name']} ({student_info['matric_no']}) was detected after curfew. Late by {late_text}.",
                    "violation",
                    related_violation_id=violation_id
                )

                # STUDENT
                notify_user(
                    cur,
                    recognized_student_id,
                    "Late Check-in Recorded",
                    f"You were detected after curfew. Late by {late_text}.",
                    "violation",
                    related_violation_id=violation_id
                )

                # =========================
                # 🚨 3 TIMES WARNING (INSERT HERE)
                # =========================

                cur.execute("""
                    SELECT COUNT(*) as total
                    FROM violations
                    WHERE user_id = %s
                    AND MONTH(violation_date) = MONTH(NOW())
                    AND YEAR(violation_date) = YEAR(NOW())
                """, (recognized_student_id,))

                result = cur.fetchone()

                if result["total"] >= 3:
                    notify_user(
                        cur,
                        recognized_student_id,
                        "Warning: Frequent Late Check-ins",
                        "You have exceeded 3 late check-ins this month.",
                        "warning"
                    )

            conn.commit()

            return jsonify({
                "success": True,
                "status": "recognized",
                "message": "Student identified successfully",
                "student_id": recognized_student_id,
                "student_name": student_info["student_name"],
                "matric_no": student_info["matric_no"],
                "block": student_info["block"],
                "room_no": student_info["room_no"],
                "confidence_score": round(best_distance, 4),
                "checkin_id": int(checkin_id),
                "is_late": is_late,
                "late_minutes": int(late_minutes),
                "violation_created": violation_created,
                "image_path": "/" + db_image_path
            })

        except Exception as e:
            if conn:
                conn.rollback()
            print("SECURITY VERIFY FACE ERROR:", e)
            return jsonify({
                "success": False,
                "status": "error",
                "message": "Face verification failed"
            }), 500

        finally:
            if cur:
                cur.close()

    @app.route("/security/profile", methods=["GET", "POST"])
    @login_required(role="security")
    def security_profile():
        conn = get_db()
        cur = conn.cursor(pymysql.cursors.DictCursor)

        # =========================
        # HANDLE UPDATE (POST)
        # =========================
        if request.method == "POST":
            name = request.form.get("officer_name")
            email = request.form.get("officer_email")
            phone = request.form.get("officer_phone")

            profile_pic = request.files.get("officer_official_pic")
            filename = None

            # -------- Profile picture upload --------
            if profile_pic and profile_pic.filename:
                filename = secure_filename(profile_pic.filename)

                upload_folder = app.config.get(
                    "UPLOAD_FOLDER",
                    "static/images/profiles"
                )

                os.makedirs(upload_folder, exist_ok=True)
                profile_pic.save(os.path.join(upload_folder, filename))

                cur.execute("""
                    UPDATE security_officers
                    SET officer_name=%s,
                        officer_email=%s,
                        officer_phone=%s,
                        officer_official_pic=%s
                    WHERE user_id=%s
                """, (name, email, phone, filename, get_current_user("security")["user_id"]))

            else:
                cur.execute("""
                    UPDATE security_officers
                    SET officer_name=%s,
                        officer_email=%s,
                        officer_phone=%s
                    WHERE user_id=%s
                """, (name, email, phone, get_current_user("security")["user_id"]))

            conn.commit()

        # =========================
        # FETCH PROFILE (GET)
        # =========================
        cur.execute("""
            SELECT
                officer_name,
                staff_id,
                officer_email,
                officer_phone,
                created_at,
                officer_official_pic
            FROM security_officers
            WHERE user_id=%s
        """, (get_current_user("security")["user_id"],))

        security = cur.fetchone()
        cur.close()

        return render_template(
            "security_profile.html",
            security=security
        )

    @app.route("/security/violations")
    @login_required(role="security")
    def security_violations():
        conn = get_db()
        cur = conn.cursor(pymysql.cursors.DictCursor)

        cur.execute("""
            SELECT
                s.student_name,
                s.matric_no AS matric_number,
                s.block,
                s.room_no AS room,
                    
                    DATE_FORMAT(
                        v.violation_date,
                        '%d %b %Y'
                    ) AS violation_date,
                    
                v.created_at,
                v.status,
                COUNT(v2.violation_id) AS violation_count
            FROM violations v
            JOIN students s ON v.user_id = s.user_id
            JOIN violations v2 ON v2.user_id = v.user_id
            GROUP BY
                v.violation_id,
                s.student_name,
                s.matric_no,
                s.block,
                s.room_no,
                v.violation_date,
                v.created_at,
                v.status
            ORDER BY v.created_at DESC
        """)

        violations = cur.fetchall()
        cur.close()

        return render_template(
            "security_violations.html",
            violations=violations
        )
    
    @app.route("/security/fines")
    @login_required(role="security")
    def security_fines():

        conn = get_db()
        cur = conn.cursor(pymysql.cursors.DictCursor)

        try:

            cur.execute("""
                SELECT
                    f.fine_id,
                    f.user_id,
                    f.amount,
                    f.reason,
                    f.payment_status,

                    DATE_FORMAT(
                        f.created_at,
                        '%d %b %Y • %h:%i %p'
                    ) AS created_at,

                    s.student_name,
                    s.matric_no,
                    s.block,
                    s.room_no

                FROM fines f

                JOIN students s
                    ON f.user_id = s.user_id

                ORDER BY f.created_at DESC
            """)

            fines = cur.fetchall()

            return render_template(
                "security_fines.html",
                fines=fines
            )

        finally:
            cur.close()

    @app.route("/security/excuse-letters")
    @login_required(role="security")
    def security_excuse_letters():

        conn = get_db()
        cur = conn.cursor(pymysql.cursors.DictCursor)

        try:

            cur.execute("""
                SELECT
                    a.appeal_id,
                    a.user_id,

                    a.reason,
                    a.status,

                    DATE_FORMAT(
                        a.submitted_at,
                        '%d %b %Y • %h:%i %p'
                    ) AS submitted_at,

                    DATE_FORMAT(
                        v.violation_date,
                        '%d %b %Y'
                    ) AS violation_date,

                    a.admin_comment,

                    s.student_name,
                    s.matric_no

                FROM appeals a

                JOIN students s
                    ON a.user_id = s.user_id

                LEFT JOIN violations v
                    ON a.violation_id = v.violation_id

                ORDER BY violation_date DESC
            """)

            letters = cur.fetchall()

            # =========================
            # STATISTICS
            # =========================
            total_letters = len(letters)

            pending_letters = len([
                l for l in letters
                if l["status"] == "Pending"
            ])

            approved_letters = len([
                l for l in letters
                if l["status"] == "Approved"
            ])

            return render_template(
                "security_excuse_letters.html",

                letters=letters,

                total_letters=total_letters,
                pending_letters=pending_letters,
                approved_letters=approved_letters
            )

        finally:
            cur.close()
    
    @app.route("/security/warning-letters")
    @login_required(role="security")
    def security_warning_letters():
        return render_template("security_warning_letters.html")

    @app.route("/security/notifications", endpoint="security_notifications")
    @login_required(role="security")
    def security_notifications():
        conn = get_db()
        cur = conn.cursor(pymysql.cursors.DictCursor)

        try:
            cur.execute("""
                SELECT
                    notification_id,
                    title,
                    message,
                    type,
                    is_read,
                    read_at,
                    created_at,
                    related_violation_id,
                    related_appeal_id
                FROM system_notifications
                WHERE user_id = %s
                ORDER BY created_at DESC
            """, (get_current_user("security")["user_id"],))
            notifications = cur.fetchall()

            unread_count = get_unread_notification_count(cur, get_current_user("security")["user_id"])

            return render_template(
                "security_notifications.html",
                notifications=notifications,
                unread_count=unread_count
            )
        finally:
            cur.close()
    
    # ======================================================
    # QR CODE
    # ======================================================
    QR_WINDOW_SECONDS = 180  # 3 minutes

    def get_qr_window(ts=None):
        if ts is None:
            ts = int(time.time())
        return ts // QR_WINDOW_SECONDS

    def generate_rotating_qr_token(qr_secret, window=None):
        if window is None:
            window = get_qr_window()

        secret_bytes = qr_secret.encode("utf-8")
        message_bytes = str(window).encode("utf-8")

        return hmac.new(secret_bytes, message_bytes, hashlib.sha256).hexdigest()

    def build_qr_base64(qr_text):
        qr = qrcode.QRCode(
            version=1,
            box_size=8,
            border=2
        )
        qr.add_data(qr_text)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")

        return f"data:image/png;base64,{encoded}"

    # ==================================================
    # STUDENT DASHBOARD
    # ==================================================
    @app.route("/student/get-rotating-qr", methods=["GET"])
    @login_required(role="student")
    def get_rotating_qr():
        user_id = get_current_user("student")["user_id"]

        conn = get_db()
        cur = conn.cursor(pymysql.cursors.DictCursor)

        try:
            cur.execute("""
                SELECT
                    user_id,
                    student_name,
                    matric_no,
                    block,
                    room_no,
                    qr_secret
                FROM students
                WHERE user_id = %s
                LIMIT 1
            """, (user_id,))
            student = cur.fetchone()

            if not student:
                return jsonify({
                    "success": False,
                    "message": "Student not found."
                }), 404

            qr_secret = student.get("qr_secret")

            if not qr_secret:
                qr_secret = secrets.token_hex(16)

                cur.execute("""
                    UPDATE students
                    SET qr_secret = %s
                    WHERE user_id = %s
                """, (qr_secret, user_id))
                conn.commit()

            token = generate_rotating_qr_token(qr_secret)
            qr_image = build_qr_base64(token)

            now_ts = int(time.time())
            expires_in = QR_WINDOW_SECONDS - (now_ts % QR_WINDOW_SECONDS)

            return jsonify({
                "success": True,
                "qr_image": qr_image,
                "expires_in": expires_in,
                "student_name": student.get("student_name", "-"),
                "matric_no": student.get("matric_no", "-"),
                "block": student.get("block", "-"),
                "room_no": student.get("room_no", "-")
            })

        except Exception as e:
            print("GET ROTATING QR ERROR:", e)
            return jsonify({
                "success": False,
                "message": "Failed to generate QR code."
            }), 500

        finally:
            cur.close()

    # ======================================================
    # VERIFY QR (SECURITY)
    # ======================================================
    @app.route("/security/verify-qr", methods=["POST"])
    @login_required(role="security")
    def verify_qr():

        try:

            data = request.get_json()

            qr_token = data.get("qr_token")

            if not qr_token:
                return jsonify({
                    "success": False,
                    "message": "QR token missing."
                }), 400

            conn = get_db()
            cur = conn.cursor(pymysql.cursors.DictCursor)

            # =========================================
            # GET STUDENTS WITH QR SECRET
            # =========================================
            cur.execute("""
                SELECT
                    user_id,
                    student_name,
                    matric_no,
                    block,
                    room_no,
                    qr_secret
                FROM students
                WHERE qr_secret IS NOT NULL
            """)

            students = cur.fetchall()

            matched_student = None

            # =========================================
            # CHECK CURRENT + PREVIOUS QR WINDOW
            # =========================================
            current_window = get_qr_window()

            for student in students:

                qr_secret = student["qr_secret"]

                current_token = generate_rotating_qr_token(
                    qr_secret,
                    current_window
                )

                previous_token = generate_rotating_qr_token(
                    qr_secret,
                    current_window - 1
                )

                if qr_token in [current_token, previous_token]:
                    matched_student = student
                    break

            # =========================================
            # INVALID QR
            # =========================================
            if not matched_student:

                return jsonify({
                    "success": False,
                    "message": "Invalid or expired QR code."
                })
            
            # =========================================
            # CHECK UNPAID FINES
            # =========================================

            cur.execute("""
                SELECT fine_id
                FROM fines
                WHERE user_id = %s
                AND payment_status = 'Unpaid'
            """, (matched_student["user_id"],))

            unpaid_fine = cur.fetchone()

            if unpaid_fine:

                return jsonify({
                    "success": False,
                    "message": "Outstanding fine detected. Payment required before check-in."
                }), 403

            # =========================================
            # GET SECURITY OFFICER
            # =========================================
            security_user = get_current_user("security")

            # =========================================
            # DETERMINE LATENESS
            # =========================================
            now = datetime.now()

            if now.hour < 6:
                curfew_base_date = now - timedelta(days=1)
            else:
                curfew_base_date = now

            curfew_time = curfew_base_date.replace(
                hour=22,
                minute=0,
                second=0,
                microsecond=0
            )

            # Use actual detected timestamp date
            violation_date = datetime.now().date()

            late_minutes = 0
            is_late = now > curfew_time

            if is_late:
                late_minutes = int(
                    (now - curfew_time).total_seconds() // 60
                )

            # =========================================
            # PREVENT DUPLICATE CHECK-IN
            # =========================================
            cur.execute("""
                SELECT checkin_id
                FROM check_in_records
                WHERE user_id = %s
                AND detected_time >= NOW() - INTERVAL 1 MINUTE
            """, (matched_student["user_id"],))

            recent = cur.fetchone()

            if recent:
                return jsonify({
                    "success": False,
                    "message": "Student already checked in recently."
                }), 400

            # =========================================
            # SAVE CHECK-IN RECORD
            # =========================================
            cur.execute("""
                INSERT INTO check_in_records (
                    user_id,
                    recognized_student_id,
                    detection_method,
                    confidence_score,
                    detection_status,
                    image_path,
                    detected_time,
                    detected_by
                )
                VALUES (%s, %s, %s, %s, %s, %s, NOW(), %s)
            """, (
                matched_student["user_id"],
                matched_student["user_id"],
                "QR",
                100.00,
                "Matched",
                None,
                security_user["user_id"]
            ))

            checkin_id = cur.lastrowid

            # =========================================
            # CREATE VIOLATION IF LATE
            # =========================================
            if is_late:
                
                # =========================================
                # CHECK APPROVED PRE-APPROVAL
                # =========================================
                cur.execute("""
                    SELECT appeal_id, status
                    FROM appeals
                    WHERE user_id = %s
                    AND submission_type = 'pre_approval'
                    AND DATE(planned_return_date) = %s
                    ORDER BY submitted_at DESC
                    LIMIT 1
                """, (
                    matched_student["user_id"],
                    violation_date
                ))

                existing_appeal = cur.fetchone()

                appeal_status = None
                appeal_id = None

                if existing_appeal:
                    appeal_id = existing_appeal["appeal_id"]
                    appeal_status = existing_appeal["status"]

                violation_status = "Unexcused"
                violation_remarks = "Late check-in detected by QR code"

                if appeal_status == "Approved":
                    violation_status = "Approved"
                    violation_remarks = "Late check-in covered by approved pre-approval"

                elif appeal_status == "Pending":
                    violation_status = "Pending"
                    violation_remarks = "Waiting for admin review of pre-approval"


                # =========================================
                # INSERT VIOLATION
                # =========================================
                cur.execute("""
                    INSERT INTO violations (
                        user_id,
                        checkin_id,
                        late_minutes,
                        violation_date,
                        status,
                        remarks
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    matched_student["user_id"],
                    checkin_id,
                    late_minutes,
                    str(violation_date),
                    violation_status,
                    violation_remarks
                ))

                violation_id = cur.lastrowid

                # =========================================
                # CONNECT APPEAL TO VIOLATION
                # =========================================
                if appeal_id:

                    cur.execute("""
                        UPDATE appeals
                        SET violation_id = %s,
                            checkin_id = %s
                        WHERE appeal_id = %s
                    """, (
                        violation_id,
                        checkin_id,
                        appeal_id
                    ))

                late_text = format_late_time(late_minutes)

                # ADMIN
                notify_role(
                    cur,
                    "admin",
                    "Curfew Violation Alert",
                    f"Student {matched_student['student_name']} ({matched_student['matric_no']}) was detected after curfew. Late by {late_text}.",
                    "violation",
                    related_violation_id=violation_id
                )

                # SECURITY
                notify_role(
                    cur,
                    "security",
                    "Late Check-in Alert",
                    f"Student {matched_student['student_name']} ({matched_student['matric_no']}) was detected after curfew. Late by {late_text}.",
                    "violation",
                    related_violation_id=violation_id
                )

                # STUDENT
                notify_user(
                    cur,
                    matched_student["user_id"],
                    "Late Check-in Recorded",
                    f"You were detected after curfew. Late by {late_text}.",
                    "violation",
                    related_violation_id=violation_id
                )

            conn.commit()

            print("QR CHECK-IN SAVED")

            # =========================================
            # SUCCESS RESPONSE
            # =========================================
            return jsonify({
                "success": True,
                "student_name": matched_student["student_name"],
                "matric_no": matched_student["matric_no"],
                "block": matched_student["block"],
                "room_no": matched_student["room_no"],
                "message": "QR verified successfully."
            })

        except Exception as e:

            import traceback
            traceback.print_exc()

            return jsonify({
                "success": False,
                "message": str(e)
            }), 500

        finally:

            if 'cur' in locals():
                cur.close()

    @app.route("/student/dashboard")
    @login_required(role="student")
    def student_dashboard():

        current_user = get_current_user("student")
        user_id = current_user["user_id"]
        username = current_user["name"]

        conn = get_db()
        cur = conn.cursor(pymysql.cursors.DictCursor)

        try:

            # =========================
            # TOTAL VIOLATIONS
            # =========================
            cur.execute("""
                SELECT COUNT(*) AS total
                FROM violations
                WHERE user_id = %s
            """, (user_id,))
            total_violations = cur.fetchone()["total"]

            # =========================
            # PENDING APPEALS
            # =========================
            cur.execute("""
                SELECT COUNT(*) AS total
                FROM appeals
                WHERE user_id = %s
                AND status = 'Pending'
            """, (user_id,))
            pending_excuse_letters = cur.fetchone()["total"]

            # =========================
            # NOTIFICATIONS
            # =========================
            notification_count = get_unread_notification_count(cur, user_id)

            # =========================
            # RECENT VIOLATIONS
            # =========================
            cur.execute("""
                SELECT
                    violation_date AS date,
                    remarks,
                    status
                FROM violations
                WHERE user_id = %s
                ORDER BY violation_date DESC
                LIMIT 4
            """, (user_id,))

            recent_violations = cur.fetchall()

            # =========================
            # RECENT UPDATES
            # =========================
            updates = []

            # Appeal updates
            cur.execute("""
                SELECT
                    status,
                    submitted_at
                FROM appeals
                WHERE user_id = %s
                ORDER BY submitted_at DESC
                LIMIT 3
            """, (user_id,))

            appeal_updates = cur.fetchall()

            for item in appeal_updates:

                if item["status"] == "Approved":
                    updates.append({
                        "icon": "fa-circle-check",
                        "color": "success",
                        "message": "Your excuse letter has been approved.",
                        "date": item["submitted_at"]
                    })

                elif item["status"] == "Unexcused":
                    updates.append({
                        "icon": "fa-circle-xmark",
                        "color": "danger",
                        "message": "Your excuse letter has been rejected.",
                        "date": item["submitted_at"]
                    })

                else:
                    updates.append({
                        "icon": "fa-clock",
                        "color": "warning",
                        "message": "Your excuse letter is pending review.",
                        "date": item["submitted_at"]
                    })

            # Warning letters
            cur.execute("""
                SELECT issued_at
                FROM warning_letters
                WHERE user_id = %s
                ORDER BY issued_at DESC
                LIMIT 2
            """, (user_id,))

            warning_updates = cur.fetchall()

            for warning in warning_updates:
                updates.append({
                    "icon": "fa-file-lines",
                    "color": "primary",
                    "message": "A new warning letter has been issued.",
                    "date": warning["issued_at"]
                })

            # =========================
            # CHECK UNPAID OVERDUE FINES
            # =========================
            cur.execute("""
                SELECT fine_id
                FROM fines
                WHERE user_id = %s
                AND payment_status = 'Unpaid'
                LIMIT 1
            """, (user_id,))

            urgent_notification = cur.fetchone()

            show_curfew_popup = session.pop(
                "show_curfew_popup",
                False
            )

            show_urgent_popup = False

            # =========================
            # STUDENT PROFILE
            # =========================
            cur.execute("""
                SELECT *
                FROM students
                WHERE user_id = %s
            """, (user_id,))

            student_profile = cur.fetchone()

            # =========================
            # PROFILE REMINDER POPUP
            # =========================
            show_profile_reminder = False

            if (
                session.get("show_profile_reminder")
                and not student_profile["student_official_pic"]
            ):
                show_profile_reminder = True

            if urgent_notification and session.get("show_urgent_popup"):

                show_urgent_popup = True

                session.pop("show_urgent_popup", None)

            # =========================
            # STUDENT PROFILE PHOTO
            # =========================
            cur.execute("""
                SELECT
                    student_official_pic
                FROM students
                WHERE user_id = %s
            """, (user_id,))

            student_profile = cur.fetchone()

            return render_template(
                "dash_student.html",

                current_user=current_user,
                username=username,
                student_profile=student_profile,
                total_violations=total_violations,
                pending_excuse_letters=pending_excuse_letters,
                notification_count=notification_count,

                recent_violations=recent_violations,
                updates=updates,

                urgent_notification=urgent_notification,

                show_curfew_popup=show_curfew_popup,
                show_urgent_popup=show_urgent_popup,

                show_profile_reminder=show_profile_reminder
            )

        finally:
            cur.close()

    @app.route("/student/profile", methods=["GET", "POST"])
    @login_required(role="student")
    def student_profile():
        conn = get_db()
        cur = conn.cursor(pymysql.cursors.DictCursor)
        user_id = get_current_user("student")["user_id"]

        try:
            if request.method == "POST":
                action = request.form.get("action")

                # =========================
                # UPDATE PROFILE INFO
                # =========================
                if action == "update_info":
                    student_name = request.form.get("name", "").strip()
                    faculty = request.form.get("faculty", "").strip()
                    block = request.form.get("block", "").strip()
                    room = request.form.get("room", "").strip()
                    phone = request.form.get("phone", "").strip()
                    email = request.form.get("email", "").strip()

                    try:
                        cur.execute("""
                            UPDATE students
                            SET student_name = %s,
                                faculty = %s,
                                block = %s,
                                room_no = %s,
                                student_phone = %s,
                                student_email = %s
                            WHERE user_id = %s
                        """, (student_name, faculty, block, room, phone, email, user_id))

                        conn.commit()
                        flash("Profile information updated successfully.", "success")

                    except Exception as e:
                        conn.rollback()
                        print("UPDATE INFO ERROR:", e)
                        flash("Failed to update profile information.", "danger")

                    return redirect(url_for("student_profile"))

                # =========================
                # CHANGE PASSWORD
                # =========================
                elif action == "change_password":
                    current_password = request.form.get("current_password")
                    new_password = request.form.get("new_password")
                    confirm_password = request.form.get("confirm_password")

                    cur.execute("SELECT password FROM users WHERE user_id = %s", (user_id,))
                    user = cur.fetchone()

                    if not user or not check_password_hash(user["password"], current_password):
                        flash("Current password is incorrect.", "danger")
                        return redirect(url_for("student_profile"))

                    if new_password != confirm_password:
                        flash("New password and confirm password do not match.", "danger")
                        return redirect(url_for("student_profile"))

                    hashed_password = generate_password_hash(new_password)

                    try:
                        cur.execute("""
                            UPDATE users
                            SET password = %s
                            WHERE user_id = %s
                        """, (hashed_password, user_id))
                        conn.commit()
                        flash("Password updated successfully.", "success")

                    except Exception as e:
                        conn.rollback()
                        print("CHANGE PASSWORD ERROR:", e)
                        flash("Failed to update password.", "danger")

                    return redirect(url_for("student_profile"))

                # =========================
                # UPLOAD PROFILE PICTURE
                # =========================
                elif action == "upload_profile_pic":

                    file = request.files.get("profile_pic")

                    # =========================
                    # NO FILE
                    # =========================
                    if not file or file.filename == "":

                        flash(
                            "Please select a profile picture.",
                            "danger"
                        )

                        return redirect(
                            url_for("student_profile")
                        )
                    
                    # =========================
                    # VALID FILE TYPES
                    # =========================
                    allowed_extensions = {
                        "png",
                        "jpg",
                        "jpeg"
                    }

                    extension = (
                        file.filename.rsplit(".", 1)[1].lower()
                        if "." in file.filename
                        else ""
                    )

                    if extension not in allowed_extensions:

                        flash(
                            "Improper photo format. "
                            "Only JPG, JPEG, and PNG images are allowed.",
                            "danger"
                        )

                        return redirect(
                            url_for("student_profile")
                        )
                    
                    # =========================
                    # FILE SIZE LIMIT
                    # =========================
                    file.seek(0, os.SEEK_END)

                    file_size = file.tell()

                    file.seek(0)

                    max_size = 2 * 1024 * 1024

                    if file_size > max_size:

                        flash(
                            "Profile picture must be below 2MB.",
                            "danger"
                        )

                        return redirect(
                            url_for("student_profile")
                        )

                    # =========================
                    # SAVE FILE
                    # =========================
                    filename = secure_filename(
                        file.filename
                    )

                    unique_filename = (
                        f"{user_id}_{filename}"
                    )

                    save_folder = os.path.join(
                        app.static_folder,
                        "images/profiles"
                    )

                    os.makedirs(
                        save_folder,
                        exist_ok=True
                    )

                    save_path = os.path.join(
                        save_folder,
                        unique_filename
                    )

                    file.save(save_path)

                    # =========================
                    # VALIDATE OFFICIAL PHOTO
                    # =========================
                    is_valid, message = validate_official_photo(
                        save_path
                    )

                    print("PHOTO VALIDATION:", is_valid, message)

                    if not is_valid:

                        # DELETE INVALID IMAGE
                        if os.path.exists(save_path):

                            os.remove(save_path)

                        # REMOVE INVALID DB REFERENCE
                        cur.execute("""
                            UPDATE students
                            SET student_official_pic = NULL
                            WHERE user_id = %s
                        """, (user_id,))

                        conn.commit()

                        flash(
                            message,
                            "danger"
                        )

                        return redirect(
                            url_for("student_profile")
                        )

                    # =========================
                    # SAVE DATABASE
                    # =========================
                    cur.execute("""
                        UPDATE students
                        SET
                            student_official_pic = %s,
                            profile_completed = 1
                        WHERE user_id = %s
                    """, (
                        unique_filename,
                        user_id
                    ))

                    conn.commit()

                    flash("Official profile picture uploaded successfully.",
                            "success"
                    )

                    return redirect(url_for("student_profile"))

            # =========================
            # LOAD STUDENT DATA
            # =========================
            cur.execute("""
                SELECT
                    u.user_id,
                    s.student_name AS name,
                    s.student_email AS email,
                    s.student_phone AS phone,                        
                    s.matric_no,
                    s.faculty,
                    s.block,
                    s.room_no AS room,
                    s.course,
                    s.student_official_pic
                FROM users u
                JOIN students s ON u.user_id = s.user_id
                WHERE u.user_id = %s
            """, (user_id,))
                            
            student = cur.fetchone()

            return render_template("student_profile.html", student=student)

        finally:
            cur.close()

    @app.route("/student/upload-face-samples", methods=["POST"])
    @login_required(role="student")
    def student_upload_face_samples():
        if "face_images" not in request.files:
            flash("No face images uploaded.", "danger")
            return redirect(url_for("student_profile"))

        files = request.files.getlist("face_images")
        user_id = get_current_user("student")["user_id"]

        student_folder = os.path.join("static", "face_samples", str(user_id))
        os.makedirs(student_folder, exist_ok=True)

        saved_count = 0

        for file in files:
            if file and file.filename:
                filename = secure_filename(file.filename)
                save_path = os.path.join(student_folder, filename)
                file.save(save_path)
                saved_count += 1

        if saved_count == 0:
            flash("No valid face images were uploaded.", "warning")
        else:
            flash(f"{saved_count} face samples uploaded successfully.", "success")

        return redirect(url_for("student_profile"))
    
    @app.route("/student/save-face-frame", methods=["POST"])
    @login_required(role="student")
    def save_face_frame():
        data = request.get_json()
        image_data = data.get("image")
        expected_pose = data.get("expected_pose", "front")

        if not image_data:
            return jsonify(success=False, message="No image received")

        try:
            # =========================
            # Decode base64 image
            # =========================
            header, encoded = image_data.split(",", 1)
            img_bytes = base64.b64decode(encoded)

            np_arr = np.frombuffer(img_bytes, np.uint8)
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

            if frame is None:
                return jsonify(success=False, message="Invalid image")

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # =========================
            # FACE DETECTION
            # =========================
            detector = get_face_detector()
            faces = detector.detectMultiScale(gray, scaleFactor=1.3, minNeighbors=5)

            if len(faces) == 0:
                return jsonify(success=True, accepted=False, message="No face detected. Please align your face.")

            if len(faces) > 1:
                return jsonify(success=True, accepted=False, message="Only one face allowed.")

            # Convert NumPy int32 values to normal Python int
            x, y, w, h = [int(v) for v in faces[0]]

            # =========================
            # SIZE CHECK
            # =========================
            if w < 120 or h < 120:
                return jsonify(success=True, accepted=False, message="Move closer to the camera.")

            # =========================
            # CENTER CHECK
            # =========================
            frame_h, frame_w = frame.shape[:2]
            frame_h = int(frame_h)
            frame_w = int(frame_w)

            face_center_x = int(x + w // 2)
            face_center_y = int(y + h // 2)

            if abs(face_center_x - frame_w // 2) > frame_w * 0.30:
                return jsonify(success=True, accepted=False, message="Center your face in the frame.")

            # =========================
            # BLUR CHECK
            # =========================
            face_crop_gray = gray[y:y+h, x:x+w]
            blur_score = float(cv2.Laplacian(face_crop_gray, cv2.CV_64F).var())

            if blur_score < 45:
                return jsonify(success=True, accepted=False, message="Image is blurry. Hold still.")

            # =========================
            # COOLDOWN CHECK
            # =========================
            current_time = float(time.time())
            last_capture_time = float(session.get("last_face_capture_time", 0))

            if current_time - last_capture_time < 1.8:
                return jsonify(success=True, accepted=False, message="Please wait and change position for the next sample.")

            # =========================
            # FACE MOVEMENT CHECK
            # =========================
            last_center_x = session.get("last_face_center_x")
            last_center_y = session.get("last_face_center_y")

            if last_center_x is not None:
                last_center_x = int(last_center_x)
            if last_center_y is not None:
                last_center_y = int(last_center_y)

            # =========================
            # SIMILARITY CHECK
            # =========================
            current_face_small = cv2.resize(face_crop_gray, (120, 120))

            last_face_path = session.get("last_face_sample_path")
            if last_face_path and os.path.exists(last_face_path):
                previous_face = cv2.imread(last_face_path, cv2.IMREAD_GRAYSCALE)
                if previous_face is not None:
                    previous_face_small = cv2.resize(previous_face, (120, 120))
                    difference = cv2.absdiff(previous_face_small, current_face_small)
                    similarity_score = float(np.mean(difference))

                    if similarity_score < 3:
                        return jsonify(
                            success=True,
                            accepted=False,
                            message="Same position detected. Please follow the next instruction."
                        )

            # =========================
            # SAVE IMAGE TO TEMP FOLDER
            # =========================
            student_id = int(get_current_user("student")["user_id"])
            save_dir = os.path.join("static", "face_temp", str(student_id))
            os.makedirs(save_dir, exist_ok=True)

            filename = f"{uuid.uuid4().hex}.jpg"
            filepath = os.path.join(save_dir, filename)

            # Save cropped face instead of full frame
            face_crop_color = frame[y:y+h, x:x+w]
            cv2.imwrite(filepath, face_crop_color)

            # Save latest accepted sample for future comparison
            latest_face_path = os.path.join(save_dir, f"latest_{student_id}.jpg")
            cv2.imwrite(latest_face_path, current_face_small)

            # Store only normal Python values in session
            session["last_face_capture_time"] = float(current_time)
            session["last_face_center_x"] = int(face_center_x)
            session["last_face_center_y"] = int(face_center_y)
            session["last_face_sample_path"] = str(latest_face_path)

            return jsonify(success=True, accepted=True, message="Sample accepted")

        except Exception as e:
            print("SAVE FACE FRAME ERROR:", e)
            return jsonify(success=False, message=str(e))
        
    @app.route("/student/finalize-face-enrollment", methods=["POST"])
    @login_required(role="student")
    def finalize_face_enrollment():
        user_id = get_current_user("student")["user_id"]
        temp_folder = os.path.join("static", "face_temp", str(user_id))
        ref_folder = os.path.join("static", "face_reference")
        os.makedirs(ref_folder, exist_ok=True)

        if not os.path.exists(temp_folder):
            return jsonify({"success": False, "message": "No captured samples found"}), 400

        embeddings = []
        saved_files = sorted(os.listdir(temp_folder))

        if not saved_files:
            return jsonify({"success": False, "message": "No captured samples found"}), 400

        reference_image_name = None

        conn = None
        cur = None

        try:
            for file_name in saved_files:
                path = os.path.join(temp_folder, file_name)
                image = face_recognition.load_image_file(path)

                face_locations = face_recognition.face_locations(image)
                if len(face_locations) != 1:
                    continue

                face_encodings = face_recognition.face_encodings(image, face_locations)
                if not face_encodings:
                    continue

                embeddings.append(face_encodings[0])

                if reference_image_name is None:
                    reference_image_name = f"user_{user_id}_{int(time.time())}.jpg"
                    ref_path = os.path.join(ref_folder, reference_image_name)
                    original = cv2.imread(path)
                    if original is not None:
                        cv2.imwrite(ref_path, original)

            if len(embeddings) < 5:
                return jsonify({
                    "success": False,
                    "message": "Not enough valid face samples. Please capture again."
                }), 400

            avg_embedding = np.mean(
                embeddings,
                axis=0
            )

            embedding_json = json.dumps(
                avg_embedding.tolist()
            )

            encrypted_embedding = encrypt_embedding(
                embedding_json
            )

            conn = get_db()
            cur = conn.cursor()

            cur.execute("SELECT template_id FROM face_templates WHERE user_id = %s", (user_id,))
            existing = cur.fetchone()

            if existing:
                cur.execute("""
                    UPDATE face_templates
                    SET embedding_data = %s,
                        reference_image = %s,
                        sample_count = %s
                    WHERE user_id = %s
                """, (encrypted_embedding, reference_image_name, len(embeddings), user_id))
            else:
                cur.execute("""
                    INSERT INTO face_templates (user_id, embedding_data, reference_image, sample_count)
                    VALUES (%s, %s, %s, %s)
                """, (user_id, encrypted_embedding, reference_image_name, len(embeddings)))

            conn.commit()

            for file_name in saved_files:
                path = os.path.join(temp_folder, file_name)
                if os.path.exists(path):
                    os.remove(path)

            return jsonify({
                "success": True,
                "message": "Face enrollment completed successfully.",
                "samples_used": len(embeddings)
            })

        except Exception as e:
            if conn:
                conn.rollback()
            print("FINALIZE FACE ENROLLMENT ERROR:", e)
            return jsonify({"success": False, "message": "Failed to finalize enrollment."}), 500

        finally:
            if cur:
                cur.close()
    
    @app.route("/student/reset-face-enrollment", methods=["POST"])
    @login_required(role="student")
    def reset_face_enrollment():
        user_id = get_current_user("student")["user_id"]
        temp_folder = os.path.join("static", "face_temp", str(user_id))

        try:
            if os.path.exists(temp_folder):
                for file_name in os.listdir(temp_folder):
                    file_path = os.path.join(temp_folder, file_name)
                    if os.path.isfile(file_path):
                        os.remove(file_path)

            session.pop("last_face_capture_time", None)
            session.pop("last_face_center_x", None)
            session.pop("last_face_center_y", None)
            session.pop("last_face_sample_path", None)

            return jsonify({"success": True, "message": "Reset successful"})
        except Exception as e:
            print("RESET FACE ENROLLMENT ERROR:", e)
            return jsonify({"success": False, "message": "Reset failed"}), 500

    @app.route("/student/violations")
    @login_required(role="student")
    def student_violation_history():
        conn = get_db()
        cur = conn.cursor(pymysql.cursors.DictCursor)
        cur.execute("""
            SELECT
                DATE_FORMAT(
                    violation_date,
                    '%%d %%b %%Y'
                ) AS violation_date,

                DATE_FORMAT(
                    created_at,
                    '%%h:%%i %%p'
                ) AS created_at,

                status

            FROM violations

            WHERE user_id=%s

            ORDER BY violation_date DESC
        """, (get_current_user("student")["user_id"],))

        violations = cur.fetchall()
        cur.close()

        formatted = [{
            "date": v["violation_date"],
            "time": v["created_at"],
            "status": v["status"]
        } for v in violations]

        return render_template("student_violation_history.html", violations=formatted)
    
    
    @app.route("/student/appeal-file/<int:appeal_id>")
    @login_required(role="student")
    def student_appeal_file(appeal_id):
        conn = get_db()
        cur = conn.cursor(pymysql.cursors.DictCursor)

        try:
            cur.execute("""
                SELECT appeal_file_path
                FROM appeals
                WHERE appeal_id = %s AND user_id = %s
            """, (appeal_id, get_current_user("student")["user_id"]))
            appeal = cur.fetchone()

            if not appeal:
                abort(404)

            stored_path = appeal.get("appeal_file_path")

            if not stored_path:
                abort(404)

            stored_path = stored_path.strip().replace("\\", "/")

            possible_paths = []

            possible_paths.append(os.path.join(app.root_path, "static", stored_path))
            possible_paths.append(os.path.join(app.root_path, "static", "uploads", "appeals", stored_path))

            file_abs_path = None
            for path in possible_paths:
                if os.path.exists(path):
                    file_abs_path = path
                    break

            if not file_abs_path:
                print("Appeal file not found.")
                print("DB value:", stored_path)
                print("Checked paths:", possible_paths)
                abort(404)

            return send_file(file_abs_path, as_attachment=False)

        finally:
            cur.close()
    
    @app.route("/student/delete-appeal/<int:appeal_id>", methods=["POST"])
    @login_required(role="student")
    def delete_appeal(appeal_id):
        conn = get_db()
        cur = conn.cursor(pymysql.cursors.DictCursor)

        try:
            # ✅ CHECK ownership + status
            cur.execute("""
                SELECT status, appeal_file_path
                FROM appeals
                WHERE appeal_id = %s AND user_id = %s
            """, (appeal_id, get_current_user("student")["user_id"]))

            appeal = cur.fetchone()

            if not appeal:
                return jsonify({"success": False, "error": "Not found"}), 404

            # ❌ BLOCK IF APPROVED
            if appeal["status"] == "Approved":
                return jsonify({"success": False, "error": "Approved appeals cannot be deleted"}), 403

            # ✅ DELETE FILE (optional but good practice)
            if appeal["appeal_file_path"]:
                file_path = os.path.join(app.root_path, "static", appeal["appeal_file_path"])
                if os.path.exists(file_path):
                    os.remove(file_path)

            # ✅ DELETE DB RECORD
            cur.execute("DELETE FROM appeals WHERE appeal_id = %s", (appeal_id,))
            conn.commit()

            return jsonify({"success": True})

        finally:
            cur.close()

    @app.route("/student/excuse-letter", methods=["GET", "POST"])
    @login_required(role="student")
    def student_excuse_letter():
        conn = get_db()
        cur = conn.cursor(pymysql.cursors.DictCursor)

        upload_folder = os.path.join(app.root_path, "static", "uploads", "appeals")
        os.makedirs(upload_folder, exist_ok=True)

        try:
            if request.method == "POST":
                action = request.form.get("submission_type")

                print("DEBUG:", action)
                print("FORM:", request.form)
                print("FILES:", request.files)

                # =========================================
                # PRE-APPROVAL
                # =========================================
                if action == "pre_approval":

                    planned_date = request.form.get("planned_return_date", "").strip()
                    expected_return_time = request.form.get("expected_return_time", "").strip()
                    reason = request.form.get("reason", "").strip()
                    planned_datetime = f"{planned_date} {expected_return_time}:00"
                    reason = request.form.get("reason", "").strip()
                    document = request.files.get("supporting_document")

                    if not planned_date or not expected_return_time or not reason:
                        flash("All fields are required.", "danger")
                        return redirect(url_for("student_excuse_letter"))

                    appeal_file_path = None

                    if document and document.filename:
                        filename_secure = secure_filename(document.filename)

                        if "." in filename_secure:
                            ext = filename_secure.rsplit(".", 1)[1].lower()
                        else:
                            ext = "pdf"  # fallback

                        filename = f"pre_{get_current_user('student')['user_id']}_{uuid.uuid4().hex}.{ext}"
                        document.save(os.path.join(upload_folder, filename))
                        appeal_file_path = f"uploads/appeals/{filename}"

                    cur.execute("""
                        INSERT INTO appeals (
                            violation_id,
                            checkin_id,
                            user_id,
                            submission_type,
                            reason,
                            planned_return_date,
                            appeal_file_path,
                            submitted_at,
                            status
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), 'Pending')
                    """, (
                        None,
                        None,
                        get_current_user("student")["user_id"],
                        "pre_approval",
                        reason,
                        planned_datetime,
                        appeal_file_path
                    ))
                    
                    cur.execute("""
                        SELECT student_name, matric_no
                        FROM students
                        WHERE user_id = %s
                    """, (get_current_user("student")["user_id"],))

                    student = cur.fetchone()

                    notify_role(
                        cur,
                        "admin",
                        "New Excuse Letter Submitted",
                         f"Student {student['student_name']} ({student['matric_no']}) submitted a pre-approval request.",
                        "appeal"
                    )

                    notify_role(
                        cur,
                        "security",
                        "Excuse Letter Submitted",
                         f"Student {student['student_name']} ({student['matric_no']}) submitted a pre-approval request.",
                        "appeal"
                    )

                    conn.commit()

                    flash("Pre-approval submitted successfully.", "success")
                    return redirect(url_for("student_excuse_letter"))

                # =========================================
                # VIOLATION EXCUSE
                # =========================================
                elif action == "violation":

                    violation_id = request.form.get("violation_id")
                    reason = request.form.get("reason", "").strip()
                    document = request.files.get("supporting_document")

                    if not violation_id or not reason:
                        flash("Violation and reason are required.", "danger")
                        return redirect(url_for("student_excuse_letter"))

                    # 🔥 GET CHECKIN_ID FROM VIOLATION
                    cur.execute("""
                        SELECT checkin_id
                        FROM violations
                        WHERE violation_id = %s
                    """, (violation_id,))
                    row = cur.fetchone()

                    checkin_id = row["checkin_id"] if row else None

                    appeal_file_path = None

                    if document and document.filename:
                        ext = secure_filename(document.filename).rsplit(".", 1)[1].lower()
                        filename = f"appeal_{get_current_user('student')['user_id']}_{uuid.uuid4().hex}.{ext}"
                        document.save(os.path.join(upload_folder, filename))
                        appeal_file_path = f"uploads/appeals/{filename}"

                    cur.execute("""
                        INSERT INTO appeals (
                            violation_id,
                            checkin_id,
                            user_id,
                            submission_type,
                            reason,
                            appeal_file_path,
                            submitted_at,
                            status
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, NOW(), 'Pending')
                    """, (
                        violation_id,
                        checkin_id,
                        get_current_user("student")["user_id"],
                        "violation",
                        reason,
                        appeal_file_path
                    ))

                    cur.execute("""
                        SELECT student_name, matric_no
                        FROM students
                        WHERE user_id = %s
                    """, (get_current_user("student")["user_id"],))

                    student = cur.fetchone()

                    notify_role(
                        cur,
                        "admin",
                        "New Excuse Letter Submitted",
                        f"Student {student['student_name']} ({student['matric_no']}) submitted an excuse letter.",
                        "appeal"
                    )

                    notify_role(
                        cur,
                        "security",
                        "Excuse Letter Submitted",
                        f"Student {student['student_name']} ({student['matric_no']}) submitted an excuse letter.",
                        "appeal"
                    )

                    conn.commit()
                    
                    flash("Excuse letter submitted successfully.", "success")
                    return redirect(url_for("student_excuse_letter"))

            # =========================================
            # GET VIOLATIONS
            # =========================================
            cur.execute("""
                SELECT v.violation_id, v.violation_date
                FROM violations v
                LEFT JOIN appeals a
                    ON a.violation_id = v.violation_id
                    AND a.user_id = v.user_id
                    AND a.submission_type = 'violation'
                WHERE v.user_id = %s
                AND a.appeal_id IS NULL
                ORDER BY v.violation_date DESC
            """, (get_current_user("student")["user_id"],))
            violations = cur.fetchall()

            # =========================================
            # GET APPEALS
            # =========================================
            cur.execute("""
                SELECT
                    a.appeal_id,
                    a.submission_type,
                    a.reason,
                    a.appeal_file_path,
                    a.submitted_at,
                    a.status,
                    a.admin_comment,
                    a.planned_return_date,
                    v.violation_date

                FROM appeals a

                LEFT JOIN violations v
                    ON a.violation_id = v.violation_id

                WHERE a.user_id = %s

                ORDER BY violation_date DESC
            """, (get_current_user("student")["user_id"],))

            appeals = cur.fetchall()

            return render_template(
                "student_excuse_letter.html",
                violations=violations,
                appeals=appeals,
            )

        finally:
            cur.close()

    @app.route("/student/acknowledge-letter/<int:warning_id>", methods=["POST"])
    @login_required(role="student")
    def student_acknowledge(warning_id):
        conn = get_db()
        cur = conn.cursor()

        data = request.get_json()
        signature = data.get("signature")

        user_id = get_current_user("student")["user_id"]

        cur.execute("""
            UPDATE warning_letters
            SET 
                student_signature = %s,
                warning_letter_status = 'Confirmed',
                acknowledged_at = NOW()
            WHERE warning_id = %s
            AND user_id = %s
            AND warning_letter_status = 'Sent to Student'
        """, (signature, warning_id, user_id))

        conn.commit()

        if cur.rowcount == 0:
            return jsonify({"success": False, "message": "Already acknowledged or invalid"})

        cur.close()

        return jsonify({
            "success": True
        })

    @app.route("/student/get-warning-letter/<int:warning_id>")
    @login_required(role="student")
    def get_warning_letter(warning_id):
        conn = get_db()
        cur = conn.cursor(pymysql.cursors.DictCursor)

        cur.execute("""
            SELECT 
                wl.*,
                s.student_name,
                s.matric_no,

                CONCAT(s.block, '-', s.room_no) AS block_room,

                v.violation_date,
                DATE_FORMAT(v.created_at, '%%h:%%i %%p') AS violation_time

            FROM warning_letters wl

            JOIN students s ON wl.user_id = s.user_id

            LEFT JOIN violations v
                ON wl.violation_id = v.violation_id

            WHERE wl.warning_id = %s
        """, (warning_id,))
        
        letter = cur.fetchone()

        return render_template("warning_letter_modal_student.html", letter=letter)

    @app.route("/student/download-warning-letter/<int:warning_id>")
    @login_required(role="student")
    def student_download_warning_letter(warning_id):

        conn = get_db()
        cur = conn.cursor(pymysql.cursors.DictCursor)

        cur.execute("""
            SELECT 
                wl.*,
                s.student_name,
                s.matric_no,
                CONCAT(s.block, '-', s.room_no) AS block_room,

                v.violation_date,
                DATE_FORMAT(v.created_at, '%%h:%%i %%p') AS violation_time

            FROM warning_letters wl

            JOIN students s
                ON wl.user_id = s.user_id

            LEFT JOIN violations v
                ON wl.violation_id = v.violation_id

            WHERE wl.warning_id = %s
            AND wl.user_id = %s

        """, (
            warning_id,
            get_current_user("student")["user_id"]
        ))

        letter = cur.fetchone()

        # 🔥 SECURITY CHECK
        if not letter:
            return "Unauthorized or not found", 404

        # 🔥 FIX DATETIME ISSUES
        from datetime import datetime

        # issued_at
        if letter.get('issued_at') and isinstance(letter['issued_at'], str):
            if letter['issued_at'] != "0000-00-00 00:00:00":
                letter['issued_at'] = datetime.strptime(letter['issued_at'], "%Y-%m-%d %H:%M:%S")
            else:
                letter['issued_at'] = None

        # violation_date
        if letter.get('violation_date') and isinstance(letter['violation_date'], str):
            letter['violation_date'] = datetime.strptime(letter['violation_date'], "%Y-%m-%d")

        # acknowledged_at (VERY IMPORTANT)
        if letter.get('acknowledged_at') and isinstance(letter['acknowledged_at'], str):
            if letter['acknowledged_at'] != "0000-00-00 00:00:00":
                letter['acknowledged_at'] = datetime.strptime(letter['acknowledged_at'], "%Y-%m-%d %H:%M:%S")
            else:
                letter['acknowledged_at'] = None

        # 🔥 RENDER SAME TEMPLATE AS ADMIN
        html = render_template("warning_letter_pdf.html", letter=letter)

        # 🔥 PDF CONFIG
        import pdfkit
        config = pdfkit.configuration(
            wkhtmltopdf=r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
        )

        # 🔥 GENERATE PDF
        pdf = pdfkit.from_string(
            html,
            False,
            configuration=config,
            options={
                'enable-local-file-access': '',
                'quiet': ''
            }
        )

        # 🔥 RETURN FILE
        response = make_response(pdf)
        response.headers["Content-Type"] = "application/pdf"
        response.headers["Content-Disposition"] = f"attachment; filename=warning_letter_{warning_id}.pdf"

        return response
    
    @app.route("/student/warning-letters")
    @login_required(role="student")
    def student_warning_letters():
        conn = get_db()
        cur = conn.cursor(pymysql.cursors.DictCursor)

        try:
            # =========================================
            # 🔥 FETCH LETTERS
            # =========================================
            cur.execute("""
                SELECT 
                    wl.*,
                    v.violation_date,
                    DATE_FORMAT(v.created_at, '%%h:%%i %%p') AS violation_time

                FROM warning_letters wl

                LEFT JOIN violations v
                    ON wl.violation_id = v.violation_id

                WHERE wl.user_id = %s
                AND wl.warning_letter_status IN ('Sent to Student', 'Confirmed')

                ORDER BY violation_date DESC
            """, (get_current_user("student")["user_id"],))

            letters = cur.fetchall()

            # =========================
            # TOTAL WARNING LETTERS
            # =========================
            cur.execute("""
                SELECT COUNT(*) AS total
                FROM warning_letters
                WHERE user_id = %s
            """, (get_current_user("student")["user_id"],))

            total_letters = cur.fetchone()["total"]

            # =========================
            # ACKNOWLEDGED LETTERS
            # =========================
            cur.execute("""
                SELECT COUNT(*) AS total
                FROM warning_letters
                WHERE user_id = %s
                AND warning_letter_status = 'Confirmed'
            """, (get_current_user("student")["user_id"],))

            acknowledged_letters = cur.fetchone()["total"]

            # =========================
            # PENDING LETTERS
            # =========================
            cur.execute("""
                SELECT COUNT(*) AS total
                FROM warning_letters
                WHERE user_id = %s
                AND warning_letter_status = 'Sent to Student'
            """, (get_current_user("student")["user_id"],))

            pending_letters = cur.fetchone()["total"]

            return render_template(
                "student_warning_letters.html",
                warning_letters=letters,
                total_letters=len(letters),
                acknowledged_letters = sum(1 for l in letters if l["warning_letter_status"] == "Confirmed"),
                pending_letters = sum(1 for l in letters if l["warning_letter_status"] == "Sent to Student")
            )

        finally:
            cur.close()

    @app.route("/student/fines")
    @login_required(role="student")
    def student_fines():
        conn = get_db()
        cur = conn.cursor(pymysql.cursors.DictCursor)

        try:

            cur.execute("""
                SELECT
                    fine_id,
                    user_id,
                    amount,
                    reason,
                    payment_status,

                    DATE_FORMAT(
                        created_at,
                        '%%d %%b %%Y • %%h:%%i %%p'
                    ) AS created_at,

                    receipt_no,

                    DATE_FORMAT(
                        paid_at,
                        '%%d %%b %%Y • %%h:%%i %%p'
                    ) AS paid_at

                FROM fines

                WHERE user_id = %s

                ORDER BY created_at ASC
            """, (get_current_user("student")["user_id"],))

            fines = cur.fetchall()

            return render_template(
                "student_fines.html",
                fines=fines
            )

        finally:
            cur.close()

    @app.route("/pay-fine/<int:fine_id>")
    @login_required(role="student")
    def pay_fine(fine_id):

        conn = get_db()
        cur = conn.cursor(pymysql.cursors.DictCursor)

        try:

            # =========================================
            # GET FINE
            # =========================================
            cur.execute("""
                SELECT *
                FROM fines
                WHERE fine_id = %s
            """, (fine_id,))

            fine = cur.fetchone()

            if not fine:
                flash("Fine not found.", "danger")
                return redirect(url_for("student_fines"))

            # =========================================
            # CREATE STRIPE CHECKOUT SESSION
            # =========================================
            checkout_session = stripe.checkout.Session.create(

                payment_method_types=['card'],

                line_items=[{
                    'price_data': {
                        'currency': 'myr',
                        'product_data': {
                            'name': 'Late Check-In Fine',
                        },
                        'unit_amount': int(float(fine["amount"]) * 100),
                    },
                    'quantity': 1,
                }],

                mode='payment',

                success_url=url_for(
                    'payment_success',
                    fine_id=fine_id,
                    _external=True
                ),

                cancel_url=url_for(
                    'student_fines',
                    _external=True
                ),
            )

            return redirect(checkout_session.url)

        finally:
            cur.close()
    
    @app.route("/payment-success/<int:fine_id>")
    @login_required(role="student")
    def payment_success(fine_id):

        conn = get_db()
        cur = conn.cursor(pymysql.cursors.DictCursor)

        try:

            # =========================================
            # CHECK IF FINE EXISTS
            # =========================================
            cur.execute("""
                SELECT *
                FROM fines
                WHERE fine_id = %s
                AND user_id = %s
            """, (
                fine_id,
                get_current_user("student")["user_id"]
            ))

            fine = cur.fetchone()

            if not fine:

                flash("Fine not found.", "danger")

                return redirect(url_for("student_fines"))

            # =========================================
            # PREVENT DUPLICATE PAYMENT
            # =========================================
            if fine["payment_status"] == "Paid":

                flash("Fine already paid.", "info")

                return redirect(url_for("student_fines"))

            # =========================================
            # UPDATE FINE STATUS
            # =========================================
            # Generate receipt number
            receipt_no = f"PRCDS-REC-{int(time.time())}"

            cur.execute("""
                UPDATE fines
                SET
                    payment_status = 'Paid',
                    receipt_no = %s,
                    paid_at = NOW()
                WHERE fine_id = %s
            """, (
                receipt_no,
                fine_id
            ))

            # =========================================
            # GET STUDENT INFO
            # =========================================
            cur.execute("""
                SELECT
                    s.student_name,
                    s.matric_no
                FROM students s
                JOIN fines f
                    ON s.user_id = f.user_id
                WHERE f.fine_id = %s
            """, (fine_id,))

            student = cur.fetchone()

            # =========================================
            # NOTIFY ADMIN
            # =========================================
            notify_role(
                cur,
                "admin",
                "Fine Payment Received",
                f"Student {student['student_name']} ({student['matric_no']}) has successfully paid their disciplinary fine.",
                "payment"
            )

            # =========================================
            # NOTIFY STUDENT
            # =========================================
            notify_user(
                cur,
                fine["user_id"],
                "Payment Successful",
                "Your disciplinary fine payment has been received successfully.",
                "payment"
            )

            conn.commit()

            flash("Payment successful! Fine has been cleared.", "success")

            return redirect(url_for("student_fines"))

        except Exception as e:

            conn.rollback()

            print("PAYMENT SUCCESS ERROR:", e)

            flash("Payment processing failed.", "danger")

            return redirect(url_for("student_fines"))

        finally:
            cur.close()
    
    @app.route("/payment-receipt/<int:fine_id>")
    @login_required(role="student")
    def payment_receipt(fine_id):

        conn = get_db()
        cur = conn.cursor(pymysql.cursors.DictCursor)

        try:

            cur.execute("""
                SELECT
                    f.*,
                    s.student_name,
                    s.matric_no,
                    s.block,
                    s.room_no
                FROM fines f
                JOIN students s
                    ON f.user_id = s.user_id
                WHERE f.fine_id = %s
            """, (fine_id,))

            receipt = cur.fetchone()

            if not receipt:

                flash("Receipt not found.", "danger")

                return redirect(
                    url_for("student_warning_letters")
                )

            return render_template(
                "payment_receipt.html",
                receipt=receipt
            )

        finally:
            cur.close()

    @app.route("/student/notifications")
    @login_required(role="student")
    def student_notifications():
        conn = get_db()
        cur = conn.cursor(pymysql.cursors.DictCursor)

        try:
            cur.execute("""
                SELECT
                    notification_id,
                    title,
                    message,
                    type,
                    is_read,
                    read_at,
                    created_at,
                    related_violation_id,
                    related_appeal_id
                FROM system_notifications
                WHERE user_id = %s
                ORDER BY created_at DESC
            """, (get_current_user("student")["user_id"],))
            notifications = cur.fetchall()

            unread_count = get_unread_notification_count(cur, get_current_user("student")["user_id"])

            return render_template(
                "student_notifications.html",
                notifications=notifications,
                unread_count=unread_count
            )
        finally:
            cur.close()
    
    # ================================
    # GLOBAL NOTIFICATION ACTIONS
    # ================================

    @app.route("/notifications/read/<int:notification_id>", methods=["POST"])
    @login_required()
    def mark_notification_read(notification_id):
        conn = get_db()
        cur = conn.cursor()

        try:
            cur.execute("""
                UPDATE system_notifications
                SET is_read = 1,
                    read_at = NOW()
                WHERE notification_id = %s
                  AND user_id = %s
            """, (notification_id, get_active_user()["user_id"]))
            conn.commit()

            return jsonify({"success": True})
        except Exception as e:
            conn.rollback()
            print("MARK NOTIFICATION READ ERROR:", e)
            return jsonify({"success": False, "message": "Failed to update notification"}), 500
        finally:
            cur.close()

    
    @app.route("/notifications/delete/<int:notification_id>", methods=["POST"])
    @login_required()
    def delete_notification(notification_id):
        conn = get_db()
        cur = conn.cursor()

        try:
            cur.execute("""
                DELETE FROM system_notifications
                WHERE notification_id = %s
                  AND user_id = %s
            """, (notification_id, get_active_user()["user_id"]))
            conn.commit()

            return jsonify({"success": True})
        except Exception as e:
            conn.rollback()
            print("DELETE NOTIFICATION ERROR:", e)
            return jsonify({"success": False, "message": "Failed to delete notification"}), 500
        finally:
            cur.close()
    
    return app

# ======================================================
# RUN
# ======================================================
app = create_app()
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
