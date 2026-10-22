"""Admin routes: dashboard, CRUD for students / teachers / subjects / classes, reports, settings."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from mysql.connector.errors import IntegrityError

from models.analytics import CLASS_LABEL, dashboard_data, get_min_attendance, student_summary
from routes.shared import reports_view
from utils.auth import hash_pw, role_required
from utils.db import execute, query, transaction
from utils.validators import CODE_RE, field, parse_int, validate_person

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.before_request
@role_required("admin")
def _admin_only():
    """Every route in this blueprint is admin-only."""


def flash_all(errors):
    for e in errors:
        flash(e, "danger")


def db_message(err, what):
    """Turn a MySQL integrity error into a friendly message."""
    if err.errno == 1062:
        return f"{what} already exists (duplicate value)."
    if err.errno == 1451:
        return f"{what} cannot be deleted because other records depend on it."
    return "Database constraint error. Please check the values."


def get_classes():
    return query(f"SELECT c.*, {CLASS_LABEL} AS label FROM classes c ORDER BY c.class_name, c.semester, c.section")


# ---------------------------------------------------------------- dashboard
@bp.route("/dashboard")
def dashboard():
    return render_template("dashboard.html", role="admin", d=dashboard_data(None))


# ------------------------------------------------ students / teachers (shared)
PEOPLE = {
    "student": {"table": "students", "code": "student_id", "label": "Student"},
    "teacher": {"table": "teachers", "code": "teacher_id", "label": "Teacher"},
}


def person_add(kind):
    cfg, errors = PEOPLE[kind], validate_person(require_password=True)
    class_id = parse_int(field("class_id"))
    if kind == "student" and not (class_id and query("SELECT id FROM classes WHERE id = %s", [class_id], one=True)):
        errors.append("Please select a valid class.")
    if errors:
        flash_all(errors)
        return
    try:
        with transaction() as cur:
            cur.execute("INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)",
                        [field("username"), hash_pw(request.form["password"]), kind])
            user_id = cur.lastrowid
            if kind == "student":
                cur.execute("INSERT INTO students (user_id, student_id, name, email, class_id) VALUES (%s,%s,%s,%s,%s)",
                            [user_id, field("code"), field("name"), field("email"), class_id])
            else:
                cur.execute("INSERT INTO teachers (user_id, teacher_id, name, email) VALUES (%s,%s,%s,%s)",
                            [user_id, field("code"), field("name"), field("email")])
        flash(f"{cfg['label']} added successfully.", "success")
    except IntegrityError as e:
        flash(db_message(e, f"{cfg['label']} ID, username or email"), "danger")


def person_edit(kind, pk):
    cfg = PEOPLE[kind]
    row = query(f"SELECT * FROM {cfg['table']} WHERE id = %s", [pk], one=True)
    if not row:
        abort(404)
    errors = validate_person(require_password=False)
    class_id = parse_int(field("class_id"))
    if kind == "student" and not (class_id and query("SELECT id FROM classes WHERE id = %s", [class_id], one=True)):
        errors.append("Please select a valid class.")
    if errors:
        flash_all(errors)
        return
    try:
        with transaction() as cur:
            cur.execute("UPDATE users SET username = %s WHERE id = %s", [field("username"), row["user_id"]])
            if request.form.get("password"):
                cur.execute("UPDATE users SET password_hash = %s WHERE id = %s",
                            [hash_pw(request.form["password"]), row["user_id"]])
            if kind == "student":
                cur.execute("UPDATE students SET student_id=%s, name=%s, email=%s, class_id=%s WHERE id=%s",
                            [field("code"), field("name"), field("email"), class_id, pk])
            else:
                cur.execute("UPDATE teachers SET teacher_id=%s, name=%s, email=%s WHERE id=%s",
                            [field("code"), field("name"), field("email"), pk])
        flash(f"{cfg['label']} updated.", "success")
    except IntegrityError as e:
        flash(db_message(e, f"{cfg['label']} ID, username or email"), "danger")


def person_delete(kind, pk):
    cfg = PEOPLE[kind]
    row = query(f"SELECT user_id FROM {cfg['table']} WHERE id = %s", [pk], one=True)
    if not row:
        abort(404)
    # deleting the login row cascades to the profile, attendance and marks rows
    execute("DELETE FROM users WHERE id = %s", [row["user_id"]])
    flash(f"{cfg['label']} deleted.", "success")


@bp.route("/students")
def students():
    class_id = parse_int(request.args.get("class_id"))
    stats = {s["id"]: s for s in student_summary(class_id=class_id)}
    rows = query(f"""SELECT s.*, u.username, {CLASS_LABEL} AS class_label
                     FROM students s JOIN users u ON u.id = s.user_id JOIN classes c ON c.id = s.class_id
                     {"WHERE s.class_id = %s" if class_id else ""} ORDER BY s.student_id""",
                 [class_id] if class_id else [])
    for r in rows:
        r["pct"], r["total"] = stats[r["id"]]["pct"], stats[r["id"]]["total"]
    return render_template("admin/students.html", rows=rows, classes=get_classes(),
                           class_id=class_id, min_att=get_min_attendance())


@bp.route("/students/add", methods=["POST"])
def student_add():
    person_add("student")
    return redirect(url_for("admin.students"))


@bp.route("/students/<int:pk>/edit", methods=["POST"])
def student_edit(pk):
    person_edit("student", pk)
    return redirect(url_for("admin.students"))


@bp.route("/students/<int:pk>/delete", methods=["POST"])
def student_delete(pk):
    person_delete("student", pk)
    return redirect(url_for("admin.students"))


@bp.route("/teachers")
def teachers():
    rows = query("""SELECT t.*, u.username,
                    (SELECT COUNT(*) FROM teacher_subjects ts WHERE ts.teacher_id = t.id) AS assignments
                    FROM teachers t JOIN users u ON u.id = t.user_id ORDER BY t.teacher_id""")
    return render_template("admin/teachers.html", rows=rows)


@bp.route("/teachers/add", methods=["POST"])
def teacher_add():
    person_add("teacher")
    return redirect(url_for("admin.teachers"))


@bp.route("/teachers/<int:pk>/edit", methods=["POST"])
def teacher_edit(pk):
    person_edit("teacher", pk)
    return redirect(url_for("admin.teachers"))


@bp.route("/teachers/<int:pk>/delete", methods=["POST"])
def teacher_delete(pk):
    person_delete("teacher", pk)
    return redirect(url_for("admin.teachers"))


# ----------------------------------------------------------------- subjects
@bp.route("/subjects")
def subjects():
    rows = query("""SELECT sub.*, (SELECT COUNT(*) FROM teacher_subjects ts WHERE ts.subject_id = sub.id) AS assigned
                    FROM subjects sub ORDER BY sub.subject_code""")
    assignments = query(f"""SELECT ts.id, sub.subject_code, sub.subject_name, t.name AS teacher_name,
                                   t.teacher_id AS teacher_code, {CLASS_LABEL} AS class_label
                            FROM teacher_subjects ts
                            JOIN subjects sub ON sub.id = ts.subject_id
                            JOIN teachers t ON t.id = ts.teacher_id
                            JOIN classes c ON c.id = ts.class_id
                            ORDER BY sub.subject_name, c.section""")
    teachers_ = query("SELECT id, teacher_id, name FROM teachers ORDER BY name")
    return render_template("admin/subjects.html", rows=rows, assignments=assignments,
                           teachers=teachers_, classes=get_classes())


def subject_errors():
    errors = []
    if not CODE_RE.match(field("subject_code")):
        errors.append("Subject code must be 2-20 characters (letters, digits, - or _).")
    if not (2 <= len(field("subject_name")) <= 100):
        errors.append("Subject name must be between 2 and 100 characters.")
    return errors


@bp.route("/subjects/add", methods=["POST"])
def subject_add():
    errors = subject_errors()
    if errors:
        flash_all(errors)
    else:
        try:
            execute("INSERT INTO subjects (subject_code, subject_name) VALUES (%s, %s)",
                    [field("subject_code").upper(), field("subject_name")])
            flash("Subject added successfully.", "success")
        except IntegrityError as e:
            flash(db_message(e, "Subject code"), "danger")
    return redirect(url_for("admin.subjects"))


@bp.route("/subjects/<int:pk>/edit", methods=["POST"])
def subject_edit(pk):
    errors = subject_errors()
    if errors:
        flash_all(errors)
    else:
        try:
            execute("UPDATE subjects SET subject_code = %s, subject_name = %s WHERE id = %s",
                    [field("subject_code").upper(), field("subject_name"), pk])
            flash("Subject updated.", "success")
        except IntegrityError as e:
            flash(db_message(e, "Subject code"), "danger")
    return redirect(url_for("admin.subjects"))


@bp.route("/subjects/<int:pk>/delete", methods=["POST"])
def subject_delete(pk):
    execute("DELETE FROM subjects WHERE id = %s", [pk])
    flash("Subject deleted (its attendance and marks were removed too).", "success")
    return redirect(url_for("admin.subjects"))


@bp.route("/subjects/assign", methods=["POST"])
def subject_assign():
    t, s, c = (parse_int(request.form.get(k)) for k in ("teacher_id", "subject_id", "class_id"))
    if not (t and s and c):
        flash("Select a teacher, subject and class.", "danger")
    else:
        try:
            # one teacher per (subject, class): re-assigning simply replaces the teacher
            execute("""INSERT INTO teacher_subjects (teacher_id, subject_id, class_id) VALUES (%s, %s, %s)
                       ON DUPLICATE KEY UPDATE teacher_id = VALUES(teacher_id)""", [t, s, c])
            flash("Teacher assigned to subject and class.", "success")
        except IntegrityError:
            flash("Invalid teacher, subject or class.", "danger")
    return redirect(url_for("admin.subjects"))


@bp.route("/subjects/assignment/<int:pk>/delete", methods=["POST"])
def assignment_delete(pk):
    execute("DELETE FROM teacher_subjects WHERE id = %s", [pk])
    flash("Assignment removed.", "success")
    return redirect(url_for("admin.subjects"))


# ------------------------------------------------------------------ classes
def class_errors():
    errors = []
    if not (2 <= len(field("class_name")) <= 50):
        errors.append("Class/programme name must be 2-50 characters.")
    sem = parse_int(field("semester"))
    if not sem or not 1 <= sem <= 12:
        errors.append("Semester must be a number between 1 and 12.")
    if not (1 <= len(field("section")) <= 10):
        errors.append("Section must be 1-10 characters.")
    return errors


@bp.route("/classes")
def classes():
    rows = query("""SELECT c.*, (SELECT COUNT(*) FROM students s WHERE s.class_id = c.id) AS student_count
                    FROM classes c ORDER BY c.class_name, c.semester, c.section""")
    return render_template("admin/classes.html", rows=rows)


@bp.route("/classes/add", methods=["POST"])
def class_add():
    errors = class_errors()
    if errors:
        flash_all(errors)
    else:
        try:
            execute("INSERT INTO classes (class_name, semester, section) VALUES (%s, %s, %s)",
                    [field("class_name"), parse_int(field("semester")), field("section").upper()])
            flash("Class created.", "success")
        except IntegrityError as e:
            flash(db_message(e, "Class"), "danger")
    return redirect(url_for("admin.classes"))


@bp.route("/classes/<int:pk>/edit", methods=["POST"])
def class_edit(pk):
    errors = class_errors()
    if errors:
        flash_all(errors)
    else:
        try:
            execute("UPDATE classes SET class_name=%s, semester=%s, section=%s WHERE id=%s",
                    [field("class_name"), parse_int(field("semester")), field("section").upper(), pk])
            flash("Class updated.", "success")
        except IntegrityError as e:
            flash(db_message(e, "Class"), "danger")
    return redirect(url_for("admin.classes"))


@bp.route("/classes/<int:pk>/delete", methods=["POST"])
def class_delete(pk):
    try:
        execute("DELETE FROM classes WHERE id = %s", [pk])
        flash("Class deleted.", "success")
    except IntegrityError:
        flash("This class still has students. Move or delete them first.", "danger")
    return redirect(url_for("admin.classes"))


# ------------------------------------------------------- reports / settings
@bp.route("/reports")
def reports():
    return reports_view("admin")


@bp.route("/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        try:
            value = float(request.form.get("min_attendance", ""))
            if not 1 <= value <= 100:
                raise ValueError
        except ValueError:
            flash("Minimum attendance must be a number between 1 and 100.", "danger")
        else:
            execute("""INSERT INTO settings (setting_key, setting_value) VALUES ('min_attendance', %s)
                       ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value)""", [f"{value:g}"])
            flash(f"Minimum attendance updated to {value:g}%.", "success")
        return redirect(url_for("admin.settings"))
    return render_template("admin/settings.html", min_att=get_min_attendance())
