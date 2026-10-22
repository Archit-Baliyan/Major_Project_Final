"""Login / logout routes."""
from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from utils.auth import DASHBOARDS, csrf_token
from utils.db import query
from utils.validators import field

bp = Blueprint("auth", __name__)


@bp.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for(DASHBOARDS[session["role"]]))
    return redirect(url_for("auth.login"))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username, password = field("username"), request.form.get("password", "")
        if not username or not password:
            flash("Please enter both username and password.", "danger")
            return render_template("login.html"), 400
        user = query("SELECT * FROM users WHERE username = %s", [username], one=True)
        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Invalid username or password.", "danger")
            return render_template("login.html"), 401

        # Load the profile row so the session knows who this person is
        name, profile_id = "Administrator", None
        if user["role"] == "student":
            p = query("SELECT id, name, class_id FROM students WHERE user_id = %s", [user["id"]], one=True)
        elif user["role"] == "teacher":
            p = query("SELECT id, name FROM teachers WHERE user_id = %s", [user["id"]], one=True)
        else:
            p = None
        if p:
            name, profile_id = p["name"], p["id"]

        session.clear()                       # avoid session fixation
        session.permanent = True
        session.update(user_id=user["id"], role=user["role"], username=user["username"],
                       name=name, profile_id=profile_id)
        csrf_token()
        flash(f"Welcome back, {name}!", "success")
        return redirect(url_for(DASHBOARDS[user["role"]]))
    return render_template("login.html")


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
