"""Code shared by the admin and teacher blueprints (the report page)."""
from flask import Response, flash, redirect, render_template, request

from models.analytics import CLASS_LABEL, get_min_attendance
from models.reports import fetch_report, parse_filters, to_csv, to_pdf
from utils.db import query


def report_options(teacher_id):
    """Dropdown options; teachers only get their own classes/subjects/students."""
    if teacher_id is None:
        students = query("SELECT id, student_id, name FROM students ORDER BY name")
        subjects = query("SELECT id, subject_code, subject_name FROM subjects ORDER BY subject_name")
        classes = query(f"SELECT c.id, {CLASS_LABEL} AS label FROM classes c ORDER BY c.class_name, c.semester, c.section")
    else:
        students = query("""SELECT id, student_id, name FROM students
                            WHERE class_id IN (SELECT class_id FROM teacher_subjects WHERE teacher_id = %s)
                            ORDER BY name""", [teacher_id])
        subjects = query("""SELECT DISTINCT sub.id, sub.subject_code, sub.subject_name FROM subjects sub
                            JOIN teacher_subjects ts ON ts.subject_id = sub.id
                            WHERE ts.teacher_id = %s ORDER BY sub.subject_name""", [teacher_id])
        classes = query(f"""SELECT DISTINCT c.id, {CLASS_LABEL} AS label FROM classes c
                            JOIN teacher_subjects ts ON ts.class_id = c.id
                            WHERE ts.teacher_id = %s ORDER BY label""", [teacher_id])
    return students, subjects, classes


def reports_view(role, teacher_id=None):
    f, errors = parse_filters(request.args)
    for e in errors:
        flash(e, "danger")
    rows = fetch_report(f, teacher_id)
    export = request.args.get("export")

    if export == "csv":
        return Response(to_csv(rows), mimetype="text/csv; charset=utf-8",
                        headers={"Content-Disposition": "attachment; filename=attendance_report.csv"})
    if export == "pdf":
        try:
            pdf = to_pdf(rows, f"Generated for role: {role}")
        except ImportError:
            flash("PDF export needs the 'reportlab' package (pip install reportlab).", "danger")
            return redirect(request.path)
        return Response(pdf, mimetype="application/pdf",
                        headers={"Content-Disposition": "attachment; filename=attendance_report.pdf"})

    students, subjects, classes = report_options(teacher_id)
    active = {k: v for k, v in f.items() if v}          # filters that are actually set
    return render_template("reports.html", role=role, rows=rows, f=f, active=active,
                           students=students, subjects=subjects, classes=classes,
                           min_att=get_min_attendance())
