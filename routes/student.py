"""Student routes: dashboard, attendance history, performance, profile."""
from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from models.analytics import CLASS_LABEL, get_min_attendance, student_dashboard, student_marks
from utils.auth import hash_pw, role_required
from utils.db import execute, query
from utils.validators import parse_date, parse_int

bp = Blueprint("student", __name__, url_prefix="/student")


@bp.before_request
@role_required("student")
def _student_only():
    """Every route in this blueprint is student-only."""


def me():
    return query(f"""SELECT s.*, u.username, {CLASS_LABEL} AS class_label
                     FROM students s JOIN users u ON u.id = s.user_id JOIN classes c ON c.id = s.class_id
                     WHERE s.id = %s""", [session["profile_id"]], one=True)


@bp.route("/dashboard")
def dashboard():
    student = me()
    return render_template("student/dashboard.html", s=student,
                           d=student_dashboard(student["id"], student["class_id"]),
                           marks=student_marks(student["id"]))


@bp.route("/attendance")
def attendance():
    student = me()
    d = student_dashboard(student["id"], student["class_id"])
    subject_id = parse_int(request.args.get("subject_id"))
    from_date, to_date = request.args.get("from_date", ""), request.args.get("to_date", "")
    sql = """SELECT a.attendance_date, a.status, sub.subject_code, sub.subject_name, t.name AS teacher_name
             FROM attendance a JOIN subjects sub ON sub.id = a.subject_id
             LEFT JOIN teachers t ON t.id = a.marked_by
             WHERE a.student_id = %s"""
    params = [student["id"]]
    if subject_id:
        sql += " AND a.subject_id = %s"; params.append(subject_id)
    if parse_date(from_date):
        sql += " AND a.attendance_date >= %s"; params.append(from_date)
    if parse_date(to_date):
        sql += " AND a.attendance_date <= %s"; params.append(to_date)
    sql += " ORDER BY a.attendance_date DESC, sub.subject_name LIMIT 500"
    return render_template("student/attendance.html", d=d, records=query(sql, params), subject_id=subject_id,
                           from_date=from_date, to_date=to_date)


@bp.route("/performance")
def performance():
    return render_template("student/performance.html", marks=student_marks(session["profile_id"]))


@bp.route("/profile", methods=["GET", "POST"])
def profile():
    if request.method == "POST":
        current, new, confirm = (request.form.get(k, "") for k in ("current", "new", "confirm"))
        user = query("SELECT password_hash FROM users WHERE id = %s", [session["user_id"]], one=True)
        if not check_password_hash(user["password_hash"], current):
            flash("Current password is incorrect.", "danger")
        elif len(new) < 6:
            flash("New password must be at least 6 characters.", "danger")
        elif new != confirm:
            flash("New password and confirmation do not match.", "danger")
        else:
            execute("UPDATE users SET password_hash = %s WHERE id = %s", [hash_pw(new), session["user_id"]])
            flash("Password changed successfully.", "success")
        return redirect(url_for("student.profile"))
    return render_template("student/profile.html", s=me(), min_att=get_min_attendance())
