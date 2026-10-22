"""All attendance / marks calculations and dashboard queries live here.

Attendance %  =  (Present classes / Total classes) * 100
Marks %       =  (Marks obtained / Total marks) * 100

Teacher accounts only see data for the (subject, class) pairs assigned to
them in `teacher_subjects`; pass teacher_id=None for admin (sees everything).
"""
from flask import current_app

from utils.db import query

# SQL fragment giving a readable class name, e.g.  "MCA Sem-1 (A)"
CLASS_LABEL = "CONCAT(c.class_name, ' Sem-', c.semester, ' (', c.section, ')')"


# ---------------------------------------------------------------- formulas
def pct(present, total):
    """Attendance percentage (0 when there are no classes yet)."""
    return round(present * 100.0 / total, 2) if total else 0.0


def marks_pct(obtained, total):
    return round(float(obtained) * 100.0 / float(total), 2) if total and float(total) > 0 else 0.0


def get_min_attendance():
    row = query("SELECT setting_value FROM settings WHERE setting_key = 'min_attendance'", one=True)
    try:
        return float(row["setting_value"])
    except (TypeError, ValueError, KeyError):
        return float(current_app.config["DEFAULT_MIN_ATTENDANCE"])


# ------------------------------------------------------------ scope helpers
def att_scope(teacher_id, a="a", s="s"):
    """Extra SQL restricting attendance rows to what a teacher teaches."""
    if teacher_id is None:
        return "", []
    sql = (" AND EXISTS (SELECT 1 FROM teacher_subjects ts WHERE ts.teacher_id = %s"
           f" AND ts.subject_id = {a}.subject_id AND ts.class_id = {s}.class_id)")
    return sql, [teacher_id]


def _clean(rows):
    for r in rows:
        r["total"] = int(r["total"] or 0)
        r["present"] = int(r["present"] or 0)
        r["absent"] = r["total"] - r["present"]
        r["pct"] = pct(r["present"], r["total"])
    return rows


# --------------------------------------------------------- student summary
def student_summary(teacher_id=None, class_id=None):
    """One row per student: total classes, present, absent, overall %."""
    sc, sp = att_scope(teacher_id)
    params = list(sp)
    sql = f"""
        SELECT s.id, s.student_id, s.name, s.class_id, {CLASS_LABEL} AS class_label,
               COUNT(a.id) AS total, COALESCE(SUM(a.status = 'Present'), 0) AS present
        FROM students s
        JOIN classes c ON c.id = s.class_id
        LEFT JOIN attendance a ON a.student_id = s.id {sc}
        WHERE 1 = 1"""
    if teacher_id is not None:
        sql += " AND s.class_id IN (SELECT class_id FROM teacher_subjects WHERE teacher_id = %s)"
        params.append(teacher_id)
    if class_id:
        sql += " AND s.class_id = %s"
        params.append(class_id)
    sql += " GROUP BY s.id, s.student_id, s.name, s.class_id, c.class_name, c.semester, c.section ORDER BY s.student_id"
    return _clean(query(sql, params))


# ------------------------------------------------- admin / teacher dashboard
def dashboard_data(teacher_id=None):
    min_att = get_min_attendance()
    students = student_summary(teacher_id)
    sc, sp = att_scope(teacher_id)

    subjects = _clean(query(f"""
        SELECT sub.subject_code, sub.subject_name, COUNT(a.id) AS total,
               COALESCE(SUM(a.status = 'Present'), 0) AS present
        FROM attendance a
        JOIN students s ON s.id = a.student_id
        JOIN subjects sub ON sub.id = a.subject_id
        WHERE 1 = 1 {sc}
        GROUP BY sub.id, sub.subject_code, sub.subject_name ORDER BY sub.subject_name""", sp))

    monthly = _clean(query(f"""
        SELECT LEFT(a.attendance_date, 7) AS month, COUNT(a.id) AS total,
               COALESCE(SUM(a.status = 'Present'), 0) AS present
        FROM attendance a JOIN students s ON s.id = a.student_id
        WHERE 1 = 1 {sc}
        GROUP BY month ORDER BY month""", sp))

    total = sum(s["total"] for s in students)
    present = sum(s["present"] for s in students)
    with_data = [s for s in students if s["total"]]
    at_risk = sorted([s for s in with_data if s["pct"] < min_att], key=lambda x: x["pct"])
    ranked = sorted(with_data, key=lambda x: x["pct"], reverse=True)

    if teacher_id is None:
        n_teachers = query("SELECT COUNT(*) AS n FROM teachers", one=True)["n"]
        n_subjects = query("SELECT COUNT(*) AS n FROM subjects", one=True)["n"]
        third = ("Total Teachers", n_teachers, "person-badge", "info")
    else:
        n_subjects = query("SELECT COUNT(DISTINCT subject_id) AS n FROM teacher_subjects WHERE teacher_id = %s",
                           [teacher_id], one=True)["n"]
        n_classes = query("SELECT COUNT(DISTINCT class_id) AS n FROM teacher_subjects WHERE teacher_id = %s",
                          [teacher_id], one=True)["n"]
        third = ("My Classes", n_classes, "diagram-3", "info")

    avg = pct(present, total)
    cards = [
        ("Total Students", len(students), "people", "primary"),
        third,
        ("Total Subjects", n_subjects, "book", "success"),
        ("Attendance Records", total, "journal-check", "warning"),
        ("Average Attendance", f"{avg}%", "graph-up-arrow", "success"),
        (f"Students Below {min_att:g}%", len(at_risk), "exclamation-triangle", "danger"),
    ]
    return {
        "min_att": min_att, "cards": cards, "avg": avg,
        "present": present, "absent": total - present, "total": total,
        "subjects": subjects, "monthly": monthly, "at_risk": at_risk,
        "top": ranked[:5], "low": ranked[::-1][:5],
        "students": students,
    }


# --------------------------------------------------------- student dashboard
def student_dashboard(student_pk, class_id):
    min_att = get_min_attendance()
    subjects = _clean(query("""
        SELECT sub.id, sub.subject_code, sub.subject_name, COUNT(a.id) AS total,
               COALESCE(SUM(a.status = 'Present'), 0) AS present
        FROM teacher_subjects ts
        JOIN subjects sub ON sub.id = ts.subject_id
        LEFT JOIN attendance a ON a.subject_id = sub.id AND a.student_id = %s
        WHERE ts.class_id = %s
        GROUP BY sub.id, sub.subject_code, sub.subject_name ORDER BY sub.subject_name""",
        [student_pk, class_id]))
    monthly = _clean(query("""
        SELECT LEFT(attendance_date, 7) AS month, COUNT(id) AS total,
               COALESCE(SUM(status = 'Present'), 0) AS present
        FROM attendance WHERE student_id = %s GROUP BY month ORDER BY month""", [student_pk]))
    total = sum(s["total"] for s in subjects)
    present = sum(s["present"] for s in subjects)
    return {
        "min_att": min_att, "subjects": subjects, "monthly": monthly,
        "total": total, "present": present, "absent": total - present,
        "overall": pct(present, total),
        "low_subjects": [s for s in subjects if s["total"] and s["pct"] < min_att],
    }


def student_marks(student_pk):
    rows = query("""
        SELECT m.assessment_type, m.assessment_name, m.marks_obtained, m.total_marks,
               sub.subject_code, sub.subject_name
        FROM marks m JOIN subjects sub ON sub.id = m.subject_id
        WHERE m.student_id = %s ORDER BY sub.subject_name, m.assessment_type, m.assessment_name""", [student_pk])
    for r in rows:
        r["pct"] = marks_pct(r["marks_obtained"], r["total_marks"])
    by_subject = {}
    for r in rows:
        by_subject.setdefault(r["subject_name"], []).append(r["pct"])
    subject_avg = [{"subject": k, "avg": round(sum(v) / len(v), 2)} for k, v in by_subject.items()]
    overall = round(sum(r["pct"] for r in rows) / len(rows), 2) if rows else 0.0
    return {"rows": rows, "subject_avg": subject_avg, "overall": overall}
