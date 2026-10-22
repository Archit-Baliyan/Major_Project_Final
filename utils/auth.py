"""Session login helpers, role-based access control and CSRF protection."""
import hmac
import secrets
from functools import wraps

from flask import abort, current_app, flash, redirect, request, session, url_for

DASHBOARDS = {
    "admin": "admin.dashboard",
    "teacher": "teacher.dashboard",
    "student": "student.dashboard",
}


def role_required(*roles):
    """Route decorator: user must be logged in AND have one of the given roles."""
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if "user_id" not in session:
                flash("Please log in to continue.", "warning")
                return redirect(url_for("auth.login"))
            if session.get("role") not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator


def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_hex(16)
    return session["_csrf"]


def csrf_protect():
    """before_request hook: every POST must carry the token from the session."""
    if not current_app.config.get("CSRF_ENABLED", True):
        return
    if request.method == "POST":
        sent = request.form.get("_csrf", "")
        expected = session.get("_csrf", "")
        if not expected or not hmac.compare_digest(sent, expected):
            abort(400, "Invalid or missing CSRF token. Please reload the page and try again.")


def hash_pw(password):
    """Salted PBKDF2-SHA256 hash - plain-text passwords are never stored."""
    from werkzeug.security import generate_password_hash
    return generate_password_hash(password, method="pbkdf2:sha256")
