"""Teacher routes: dashboard, mark/edit attendance, history, students, marks, reports."""
from decimal import Decimal, InvalidOperation

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from models.analytics import CLASS_LABEL, dashboard_data, get_min_attendance, student_summary
from routes.shared import reports_view
from utils.auth import role_required
from utils.db import query, transaction
from utils.validators import field, parse_date, parse_int, today

bp = Blueprint("teacher", __name__, url_prefix="/teacher")

ASSESSMENT_TYPES = ["Assignment", "Internal", "Quiz", "Exam"]

# INSERT ... ON DUPLICATE KEY UPDATE = "mark if new, otherwise edit the existing row".
# Combined with the UNIQUE key on (student, subject, date) this prevents duplicates.
UPSERT_ATTENDANCE = """
    INSERT INTO attendance (student_id, subject_id, attendance_date, status, marked_by)
    VALUES (%s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE status = VALUES(status), marked_by = VALUES(marked_by)"""


@bp.before_request
@role_required("teacher")
def _teacher_only():
    """Every route in this blueprint is teacher-only."""


def teacher_id():
    return session["profile_id"]


def get_assignments():
    """(subject, class) pairs this teacher is allowed to work with."""
    return query(f"""
        SELECT ts.id, ts.subject_id, ts.class_id, sub.subject_code, sub.subject_name,
               {CLASS_LABEL} AS class_label
        FROM teacher_subjects ts
        JOIN subjects sub ON sub.id = ts.subject_id
        JOIN classes c ON c.id = ts.class_id
        WHERE ts.teacher_id = %s ORDER BY sub.subject_name, c.section""", [teacher_id()])


def find_assignment(assignments, ts_id):
    return next((a for a in assignments if a["id"] == ts_id), None)


@bp.route("/dashboard")
def dashboard():
    return render_template("dashboard.html", role="teacher", d=dashboard_data(teacher_id()),
                           assignments=get_assignments())


# --------------------------------------------------------------- attendance
@bp.route("/attendance", methods=["GET", "POST"])
def attendance():
    assignments = get_assignments()
    src = request.form if request.method == "POST" else request.args
    ts_id = parse_int(src.get("ts"))
    date_text = src.get("date") or today().isoformat()
    assignment = find_assignment(assignments, ts_id) if ts_id else None
    day = parse_date(date_text)

    if request.method == "POST":
        if not assignment:
            flash("Please select one of your subjects/classes.", "danger")
            return redirect(url_for("teacher.attendance"))
        if not day or day > today():
            flash("Enter a valid date (future dates are not allowed).", "danger")
            return redirect(url_for("teacher.attendance", ts=ts_id))
        students = query("SELECT id FROM students WHERE class_id = %s", [assignment["class_id"]])
        rows = []
        for s in students:
            status = request.form.get(f"status_{s['id']}")
            if status not in ("Present", "Absent"):
                flash("Every student must be marked Present or Absent.", "danger")
                return redirect(url_for("teacher.attendance", ts=ts_id, date=day.isoformat()))
            rows.append([s["id"], assignment["subject_id"], day, status, teacher_id()])
        if not rows:
            flash("This class has no students.", "warning")
        else:
            with transaction() as cur:
                for r in rows:
                    cur.execute(UPSERT_ATTENDANCE, r)
            present = sum(1 for r in rows if r[3] == "Present")
            flash(f"Attendance saved for {day:%d %b %Y}: {present} present, {len(rows) - present} absent.", "success")
        return redirect(url_for("teacher.attendance", ts=ts_id, date=day.isoformat()))

    if not day:
        flash("Invalid date. Showing today instead.", "warning")
        day = today()
    students, already = [], False
    if assignment:
        students = query("""
            SELECT s.id, s.student_id, s.name, a.status
            FROM students s
            LEFT JOIN attendance a ON a.student_id = s.id AND a.subject_id = %s AND a.attendance_date = %s
            WHERE s.class_id = %s ORDER BY s.student_id""",
                         [assignment["subject_id"], day, assignment["class_id"]])
        already = any(s["status"] for s in students)
    return render_template("teacher/attendance.html", assignments=assignments, assignment=assignment,
                           ts_id=ts_id, date=day.isoformat(), max_date=today().isoformat(),
                           students=students, already=already)


@bp.route("/attendance/history")
def history():
    assignments = get_assignments()
    ts_id = parse_int(request.args.get("ts"))
    from_date, to_date = request.args.get("from_date", ""), request.args.get("to_date", "")
    sql = f"""
        SELECT a.attendance_date, ts.id AS ts_id, sub.subject_code, sub.subject_name,
               {CLASS_LABEL} AS class_label, COUNT(a.id) AS total, SUM(a.status = 'Present') AS present
        FROM attendance a
        JOIN students s ON s.id = a.student_id
        JOIN teacher_subjects ts ON ts.subject_id = a.subject_id AND ts.class_id = s.class_id
        JOIN subjects sub ON sub.id = a.subject_id
        JOIN classes c ON c.id = s.class_id
        WHERE ts.teacher_id = %s"""
    params = [teacher_id()]
    if ts_id:
        sql += " AND ts.id = %s"; params.append(ts_id)
    if parse_date(from_date):
        sql += " AND a.attendance_date >= %s"; params.append(from_date)
    if parse_date(to_date):
        sql += " AND a.attendance_date <= %s"; params.append(to_date)
    sql += (" GROUP BY a.attendance_date, ts.id, sub.subject_code, sub.subject_name, c.class_name, c.semester, c.section"
            " ORDER BY a.attendance_date DESC, sub.subject_name LIMIT 300")
    rows = query(sql, params)
    for r in rows:
        r["present"] = int(r["present"])
        r["absent"] = r["total"] - r["present"]
    return render_template("teacher/history.html", rows=rows, assignments=assignments, ts_id=ts_id,
                           from_date=from_date, to_date=to_date)


# ----------------------------------------------------------------- students
@bp.route("/students")
def students():
    assignments = get_assignments()
    class_id = parse_int(request.args.get("class_id"))
    classes = {a["class_id"]: a["class_label"] for a in assignments}
    rows = student_summary(teacher_id(), class_id if class_id in classes else None)
    marks = {r["student_id"]: r for r in query("""
        SELECT m.student_id, ROUND(AVG(m.marks_obtained * 100 / m.total_marks), 2) AS avg_pct
        FROM marks m JOIN teacher_subjects ts ON ts.subject_id = m.subject_id
        JOIN students s ON s.id = m.student_id AND s.class_id = ts.class_id
        WHERE ts.teacher_id = %s GROUP BY m.student_id""", [teacher_id()])}
    for r in rows:
        r["marks_pct"] = marks.get(r["id"], {}).get("avg_pct")
    return render_template("teacher/students.html", rows=rows, classes=classes, class_id=class_id,
                           min_att=get_min_attendance())


# -------------------------------------------------------------------- marks
@bp.route("/marks", methods=["GET", "POST"])
def marks():
    assignments = get_assignments()
    src = request.form if request.method == "POST" else request.args
    ts_id = parse_int(src.get("ts"))
    assignment = find_assignment(assignments, ts_id) if ts_id else None

    if request.method == "POST":
        name, a_type = field("assessment_name"), field("assessment_type")
        errors = []
        if not assignment:
            errors.append("Select one of your subjects/classes.")
        if a_type not in ASSESSMENT_TYPES:
            errors.append("Select a valid assessment type.")
        if not (1 <= len(name) <= 100):
            errors.append("Assessment name is required (max 100 characters).")
        try:
            total = Decimal(field("total_marks"))
            if total <= 0 or total > 1000:
                raise InvalidOperation
        except InvalidOperation:
            errors.append("Total marks must be a positive number.")
            total = None
        rows = []
        if not errors:
            for s in query("SELECT id, name FROM students WHERE class_id = %s", [assignment["class_id"]]):
                raw = request.form.get(f"marks_{s['id']}", "").strip()
                if raw == "":
                    continue                         # blank = not entered
                try:
                    value = Decimal(raw)
                except InvalidOperation:
                    errors.append(f"Marks for {s['name']} must be a number.")
                    continue
                if value < 0 or value > total:
                    errors.append(f"Marks for {s['name']} must be between 0 and {total}.")
                    continue
                rows.append([s["id"], assignment["subject_id"], a_type, name, value, total, teacher_id()])
        if not errors and not rows:
            errors.append("Enter marks for at least one student.")
        if errors:
            for e in errors:
                flash(e, "danger")
            return redirect(url_for("teacher.marks", ts=ts_id))
        with transaction() as cur:
            for r in rows:
                cur.execute("""INSERT INTO marks (student_id, subject_id, assessment_type, assessment_name,
                                                  marks_obtained, total_marks, entered_by)
                               VALUES (%s,%s,%s,%s,%s,%s,%s)
                               ON DUPLICATE KEY UPDATE assessment_type = VALUES(assessment_type),
                                   marks_obtained = VALUES(marks_obtained),
                                   total_marks = VALUES(total_marks), entered_by = VALUES(entered_by)""", r)
        flash(f"Saved marks for {len(rows)} student(s) in '{name}'.", "success")
        return redirect(url_for("teacher.marks", ts=ts_id, assessment=name))

    ctx = dict(assignments=assignments, assignment=assignment, ts_id=ts_id, types=ASSESSMENT_TYPES,
               students=[], assessments=[], performance=[], prefill={"name": "", "type": "Assignment", "total": ""})
    if assignment:
        chosen = request.args.get("assessment", "").strip()
        ctx["students"] = query("""
            SELECT s.id, s.student_id, s.name, m.marks_obtained, m.assessment_type, m.total_marks
            FROM students s
            LEFT JOIN marks m ON m.student_id = s.id AND m.subject_id = %s AND m.assessment_name = %s
            WHERE s.class_id = %s ORDER BY s.student_id""",
                                [assignment["subject_id"], chosen, assignment["class_id"]])
        first = next((s for s in ctx["students"] if s["marks_obtained"] is not None), None)
        if first:
            ctx["prefill"] = {"name": chosen, "type": first["assessment_type"], "total": f"{first['total_marks']:g}"}
        ctx["assessments"] = query("""
            SELECT m.assessment_name, m.assessment_type, m.total_marks, COUNT(*) AS entered,
                   ROUND(AVG(m.marks_obtained * 100 / m.total_marks), 2) AS avg_pct
            FROM marks m JOIN students s ON s.id = m.student_id
            WHERE m.subject_id = %s AND s.class_id = %s
            GROUP BY m.assessment_name, m.assessment_type, m.total_marks
            ORDER BY MIN(m.created_at), m.assessment_name""", [assignment["subject_id"], assignment["class_id"]])
        ctx["performance"] = query("""
            SELECT s.student_id, s.name, COUNT(m.id) AS entered,
                   ROUND(AVG(m.marks_obtained * 100 / m.total_marks), 2) AS avg_pct
            FROM students s LEFT JOIN marks m ON m.student_id = s.id AND m.subject_id = %s
            WHERE s.class_id = %s GROUP BY s.id, s.student_id, s.name ORDER BY s.student_id""",
                                   [assignment["subject_id"], assignment["class_id"]])
    return render_template("teacher/marks.html", **ctx)


# ------------------------------------------------------------------ reports
@bp.route("/reports")
def reports():
    return reports_view("teacher", teacher_id())
