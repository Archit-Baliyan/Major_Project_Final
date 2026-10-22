"""Server-side validation helpers (never trust only the browser checks)."""
import re
from datetime import date, datetime

from flask import request

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
CODE_RE = re.compile(r"^[A-Za-z0-9_-]{2,20}$")


def field(name):
    """Trimmed value of a form field ('' if missing)."""
    return request.form.get(name, "").strip()


def parse_date(text):
    """'YYYY-MM-DD' -> date, or None if invalid."""
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def parse_int(text):
    try:
        return int(text)
    except (ValueError, TypeError):
        return None


def validate_person(require_password):
    """Common validation for student/teacher forms. Returns list of error strings."""
    errors = []
    if not CODE_RE.match(field("code")):
        errors.append("ID must be 2-20 characters (letters, digits, - or _).")
    if not CODE_RE.match(field("username")):
        errors.append("Username must be 2-20 characters (letters, digits, - or _).")
    if not (2 <= len(field("name")) <= 100):
        errors.append("Name must be between 2 and 100 characters.")
    if not EMAIL_RE.match(field("email")) or len(field("email")) > 120:
        errors.append("Enter a valid email address.")
    pw = request.form.get("password", "")
    if (require_password or pw) and len(pw) < 6:
        errors.append("Password must be at least 6 characters.")
    return errors


def today():
    return date.today()
