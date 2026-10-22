"""Attendance report query + CSV / PDF export helpers."""
import csv
import io

from models.analytics import CLASS_LABEL, att_scope, pct
from utils.db import query
from utils.validators import parse_date, parse_int

CSV_HEADER = ["Student Name", "Student ID", "Class", "Subject", "Total Classes", "Present", "Absent", "Attendance %"]


def parse_filters(args):
    """Read + validate report filters from the query string."""
    f = {
        "from_date": args.get("from_date", "").strip(),
        "to_date": args.get("to_date", "").strip(),
        "student_id": parse_int(args.get("student_id")),
        "subject_id": parse_int(args.get("subject_id")),
        "class_id": parse_int(args.get("class_id")),
    }
    errors = []
    for key in ("from_date", "to_date"):
        if f[key] and not parse_date(f[key]):
            errors.append("Invalid date format.")
            f[key] = ""
    if f["from_date"] and f["to_date"] and f["from_date"] > f["to_date"]:
        errors.append("'From' date cannot be after 'To' date.")
        f["from_date"] = f["to_date"] = ""
    return f, errors


def fetch_report(f, teacher_id=None):
    sc, sp = att_scope(teacher_id)
    sql = f"""
        SELECT s.id AS sid, s.name, s.student_id, {CLASS_LABEL} AS class_label,
               sub.subject_code, sub.subject_name,
               COUNT(a.id) AS total, SUM(a.status = 'Present') AS present
        FROM attendance a
        JOIN students s ON s.id = a.student_id
        JOIN classes c ON c.id = s.class_id
        JOIN subjects sub ON sub.id = a.subject_id
        WHERE 1 = 1 {sc}"""
    params = list(sp)
    if f["from_date"]:
        sql += " AND a.attendance_date >= %s"; params.append(f["from_date"])
    if f["to_date"]:
        sql += " AND a.attendance_date <= %s"; params.append(f["to_date"])
    if f["student_id"]:
        sql += " AND s.id = %s"; params.append(f["student_id"])
    if f["subject_id"]:
        sql += " AND a.subject_id = %s"; params.append(f["subject_id"])
    if f["class_id"]:
        sql += " AND s.class_id = %s"; params.append(f["class_id"])
    sql += (" GROUP BY s.id, s.name, s.student_id, c.class_name, c.semester, c.section,"
            " sub.id, sub.subject_code, sub.subject_name ORDER BY s.name, sub.subject_name")
    rows = query(sql, params)
    for r in rows:
        r["total"] = int(r["total"])
        r["present"] = int(r["present"])
        r["absent"] = r["total"] - r["present"]
        r["pct"] = pct(r["present"], r["total"])
    return rows


def _table_rows(rows):
    return [[r["name"], r["student_id"], r["class_label"], f"{r['subject_code']} - {r['subject_name']}",
             r["total"], r["present"], r["absent"], r["pct"]] for r in rows]


def to_csv(rows):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(CSV_HEADER)
    writer.writerows(_table_rows(rows))
    return "\ufeff" + buf.getvalue()      # BOM so Excel opens UTF-8 correctly


def to_pdf(rows, subtitle=""):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    out = io.BytesIO()
    doc = SimpleDocTemplate(out, pagesize=landscape(A4), leftMargin=24, rightMargin=24, topMargin=24, bottomMargin=24)
    styles = getSampleStyleSheet()
    data = [CSV_HEADER] + _table_rows(rows)
    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
    ]))
    doc.build([Paragraph("Attendance Report", styles["Title"]), Paragraph(subtitle or " ", styles["Normal"]),
               Spacer(1, 10), table])
    return out.getvalue()
