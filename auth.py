"""Authentication blueprint and Flask-Login integration."""
import sqlite3
from urllib.parse import urlsplit
from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash
from database import User, get_db, get_user
from utils import normalize_email, normalize_username, utc_now, valid_email, valid_username
auth_bp = Blueprint("auth", __name__)
login_manager = LoginManager()

def _safe_next_url(value):
    target = urlsplit(value or "")
    return target.scheme == "" and target.netloc == "" and target.path.startswith("/")

@login_manager.user_loader
def load_user(user_id):
    try: return get_user(int(user_id))
    except (TypeError, ValueError): return None

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated: return redirect(url_for("routes.home"))
    error = None
    if request.method == "POST":
        identity, password = request.form.get("identity", "").strip().lower(), request.form.get("password", "")
        connection = get_db()
        try: row = connection.execute("SELECT * FROM users WHERE username = ? OR email = ?", (identity, identity)).fetchone()
        finally: connection.close()
        if row and check_password_hash(row["password"], password):
            login_user(User(row), remember=request.form.get("remember") == "on")
            destination = request.args.get("next")
            return redirect(destination if _safe_next_url(destination) else url_for("routes.home"))
        error = "Incorrect username, email, or password."
    return render_template("login.html", error=error)

@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated: return redirect(url_for("routes.home"))
    error = None
    if request.method == "POST":
        username, email, password = normalize_username(request.form.get("username")), normalize_email(request.form.get("email")), request.form.get("password", "")
        if not valid_username(username): error = "Use 3–32 letters, numbers, or underscores for your username."
        elif not valid_email(email): error = "Enter a valid email address."
        elif len(password) < 8: error = "Password must be at least 8 characters."
        else:
            connection = get_db()
            try:
                connection.execute("INSERT INTO users (username, email, password, created_at) VALUES (?, ?, ?, ?)", (username, email, generate_password_hash(password), utc_now()))
                connection.commit()
                return redirect(url_for("auth.login"))
            except sqlite3.IntegrityError: error = "That username or email is already registered."
            finally: connection.close()
    return render_template("signup.html", error=error)

@auth_bp.post("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
