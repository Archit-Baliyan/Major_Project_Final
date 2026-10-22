"""Automated test cases.  Run from the project folder with:

    python -m unittest tests.test_app -v

The tests use a separate database called  smart_attendance_test  (created and
filled with the demo data automatically), so your real data is never touched.
"""
import csv
import io
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "database"))

import mysql.connector  # noqa: E402

from app import create_app  # noqa: E402
from init_db import init_db  # noqa: E402
from models.analytics import marks_pct, pct  # noqa: E402

TEST_DB = "smart_attendance_test"
TODAY = date.today().isoformat()


class BaseCase(unittest.TestCase):
    def setUp(self):
        init_db(TEST_DB)                                   # fresh schema + demo data for every test
        self.app = create_app({"DB_NAME": TEST_DB, "CSRF_ENABLED": False, "TESTING": True})
        self.client = self.app.test_client()

    # helpers ---------------------------------------------------------
    def login(self, username, password, client=None):
        return (client or self.client).post("/login", data={"username": username, "password": password})

    def rows(self, sql, params=()):
        conn = mysql.connector.connect(host=self.app.config["DB_HOST"], user=self.app.config["DB_USER"],
                                       password=self.app.config["DB_PASSWORD"], database=TEST_DB, use_pure=True)
        cur = conn.cursor(dictionary=True)
        cur.execute(sql, params)
        out = cur.fetchall()
        conn.close()
        return out

    def class1_status_form(self, absent_first=True):
        ids = [r["id"] for r in self.rows("SELECT id FROM students WHERE class_id = 1 ORDER BY id")]
        form = {"ts": 1, "date": TODAY}
        for i, sid in enumerate(ids):
            form[f"status_{sid}"] = "Absent" if (absent_first and i == 0) else "Present"
        return form, ids


class TestAuthentication(BaseCase):
    def test_01_login_success_all_roles(self):
        for user, pw, target in [("admin", "admin123", "/admin/dashboard"),
                                 ("teacher1", "teacher123", "/teacher/dashboard"),
                                 ("MCA2601", "student123", "/student/dashboard")]:
            c = self.app.test_client()
            r = self.login(user, pw, c)
            self.assertEqual(r.status_code, 302, user)
            self.assertTrue(r.headers["Location"].endswith(target), user)

    def test_02_invalid_login(self):
        r = self.login("admin", "wrong-password")
        self.assertEqual(r.status_code, 401)
        self.assertIn(b"Invalid username or password", r.data)
        r = self.login("nobody", "x")
        self.assertEqual(r.status_code, 401)

    def test_03_sql_injection_login_fails(self):
        r = self.login("' OR '1'='1' -- ", "anything")
        self.assertEqual(r.status_code, 401)

    def test_04_role_authorization(self):
        anon = self.client.get("/admin/dashboard")
        self.assertEqual(anon.status_code, 302)                       # not logged in -> login page
        self.assertIn("/login", anon.headers["Location"])
        student, teacher = self.app.test_client(), self.app.test_client()
        self.login("MCA2601", "student123", student)
        self.login("teacher1", "teacher123", teacher)
        self.assertEqual(student.get("/admin/dashboard").status_code, 403)
        self.assertEqual(student.get("/teacher/attendance").status_code, 403)
        self.assertEqual(teacher.get("/admin/students").status_code, 403)
        self.assertEqual(teacher.get("/student/dashboard").status_code, 403)

    def test_05_logout_clears_session(self):
        self.login("admin", "admin123")
        self.client.post("/logout")
        self.assertEqual(self.client.get("/admin/dashboard").status_code, 302)

    def test_06_csrf_blocks_post_without_token(self):
        strict = create_app({"DB_NAME": TEST_DB, "CSRF_ENABLED": True}).test_client()
        self.assertEqual(strict.post("/login", data={"username": "admin", "password": "admin123"}).status_code, 400)

    def test_07_passwords_are_hashed(self):
        for row in self.rows("SELECT password_hash FROM users"):
            self.assertTrue(row["password_hash"].startswith("pbkdf2:"))
            self.assertNotIn("admin123", row["password_hash"])


class TestAdminModules(BaseCase):
    def setUp(self):
        super().setUp()
        self.login("admin", "admin123")

    def test_10_add_student(self):
        r = self.client.post("/admin/students/add", data={
            "code": "MCA2699", "username": "MCA2699", "name": "Test Student", "email": "test.student@example.com",
            "class_id": 1, "password": "secret123"}, follow_redirects=True)
        self.assertIn(b"Student added successfully", r.data)
        self.assertEqual(len(self.rows("SELECT * FROM students WHERE student_id = 'MCA2699'")), 1)
        self.assertEqual(self.login("MCA2699", "secret123", self.app.test_client()).status_code, 302)

    def test_11_add_student_validation_and_duplicates(self):
        bad = self.client.post("/admin/students/add", data={"code": "X", "username": "", "name": "A",
                               "email": "not-an-email", "class_id": 1, "password": "123"}, follow_redirects=True)
        self.assertIn(b"valid email", bad.data)
        dup = self.client.post("/admin/students/add", data={"code": "MCA2601", "username": "newuser", "name": "Dup Student",
                               "email": "dup@example.com", "class_id": 1, "password": "secret123"}, follow_redirects=True)
        self.assertIn(b"already exists", dup.data)

    def test_12_add_subject(self):
        r = self.client.post("/admin/subjects/add", data={"subject_code": "NET106", "subject_name": "Computer Networks"},
                             follow_redirects=True)
        self.assertIn(b"Subject added successfully", r.data)
        self.assertEqual(len(self.rows("SELECT * FROM subjects WHERE subject_code = 'NET106'")), 1)

    def test_13_delete_student_cascades(self):
        sid = self.rows("SELECT id FROM students WHERE student_id = 'MCA2601'")[0]["id"]
        self.client.post(f"/admin/students/{sid}/delete")
        self.assertEqual(self.rows("SELECT COUNT(*) n FROM attendance WHERE student_id = %s", (sid,))[0]["n"], 0)
        self.assertEqual(self.rows("SELECT COUNT(*) n FROM users WHERE username = 'MCA2601'")[0]["n"], 0)

    def test_14_settings_change_threshold(self):
        self.client.post("/admin/settings", data={"min_attendance": "85"})
        self.assertEqual(self.rows("SELECT setting_value v FROM settings")[0]["v"], "85")
        bad = self.client.post("/admin/settings", data={"min_attendance": "500"}, follow_redirects=True)
        self.assertIn(b"between 1 and 100", bad.data)


class TestAttendance(BaseCase):
    def setUp(self):
        super().setUp()
        self.login("teacher1", "teacher123")

    def test_20_mark_attendance(self):
        form, ids = self.class1_status_form()
        r = self.client.post("/teacher/attendance", data=form, follow_redirects=True)
        self.assertIn(b"Attendance saved", r.data)
        rows = self.rows("SELECT status FROM attendance WHERE subject_id = 1 AND attendance_date = %s "
                         "AND student_id IN (%s)" % ("%s", ",".join(map(str, ids))), (TODAY,))
        self.assertEqual(len(rows), 10)
        self.assertEqual(sum(1 for r in rows if r["status"] == "Absent"), 1)

    def test_21_duplicate_attendance_prevented_and_edit_works(self):
        form, ids = self.class1_status_form(absent_first=True)
        self.client.post("/teacher/attendance", data=form)
        form2, _ = self.class1_status_form(absent_first=False)     # everyone present this time
        self.client.post("/teacher/attendance", data=form2)
        rows = self.rows("SELECT status FROM attendance WHERE subject_id = 1 AND attendance_date = %s "
                         "AND student_id IN (%s)" % ("%s", ",".join(map(str, ids))), (TODAY,))
        self.assertEqual(len(rows), 10)                                # still 10 rows, not 20
        self.assertTrue(all(r["status"] == "Present" for r in rows))   # and the edit was applied

    def test_22_database_unique_key_blocks_duplicates(self):
        form, ids = self.class1_status_form()
        self.client.post("/teacher/attendance", data=form)
        with self.assertRaises(mysql.connector.IntegrityError):
            self.rows("INSERT INTO attendance (student_id, subject_id, attendance_date, status, marked_by) "
                      "VALUES (%s, 1, %s, 'Present', 1)", (ids[0], TODAY))

    def test_23_future_date_rejected(self):
        form, _ = self.class1_status_form()
        form["date"] = "2099-01-01"
        r = self.client.post("/teacher/attendance", data=form, follow_redirects=True)
        self.assertIn(b"future dates are not allowed", r.data)

    def test_24_teacher_cannot_mark_other_teachers_subject(self):
        form, _ = self.class1_status_form()
        form["ts"] = 4                                                # DSA104 belongs to teacher2
        r = self.client.post("/teacher/attendance", data=form, follow_redirects=True)
        self.assertIn(b"select one of your subjects", r.data)
        self.assertEqual(self.rows("SELECT COUNT(*) n FROM attendance WHERE subject_id = 4 AND attendance_date = %s",
                                   (TODAY,))[0]["n"], 0)

    def test_25_attendance_percentage_formula(self):
        self.assertEqual(pct(45, 60), 75.0)
        self.assertEqual(pct(0, 0), 0.0)                              # no classes -> 0, no crash
        self.assertEqual(pct(2, 3), 66.67)
        # value shown by the app must equal a hand-written SQL calculation
        db = self.rows("SELECT SUM(status='Present') p, COUNT(*) t FROM attendance WHERE student_id = 1")[0]
        with self.app.app_context():
            from models.analytics import student_summary
            s = next(x for x in student_summary() if x["id"] == 1)
        self.assertEqual(s["pct"], pct(int(db["p"]), db["t"]))


class TestSmartFeatures(BaseCase):
    def test_30_low_attendance_warning_shown_only_when_below_threshold(self):
        low, high = self.app.test_client(), self.app.test_client()
        self.login("MCA2613", "student123", low)       # about 55% attendance in demo data
        self.login("MCA2611", "student123", high)      # about 97% attendance in demo data
        self.assertIn(b"Low attendance warning", low.get("/student/dashboard").data)
        self.assertNotIn(b"Low attendance warning", high.get("/student/dashboard").data)

    def test_31_students_at_risk_on_admin_dashboard(self):
        self.login("admin", "admin123")
        html = self.client.get("/admin/dashboard").data.decode()
        self.assertIn("Manish Tiwari", html)           # low-attendance student is listed
        self.assertIn("Students at Risk", html)

    def test_32_threshold_is_configurable(self):
        self.login("admin", "admin123")
        with self.app.app_context():
            from models.analytics import dashboard_data
            before = len(dashboard_data()["at_risk"])
        self.client.post("/admin/settings", data={"min_attendance": "90"})
        with self.app.app_context():
            after = len(dashboard_data()["at_risk"])
        self.assertGreater(after, before)


class TestMarks(BaseCase):
    def test_40_marks_percentage_formula(self):
        self.assertEqual(marks_pct(45, 50), 90.0)
        self.assertEqual(marks_pct(17, 20), 85.0)
        self.assertEqual(marks_pct(0, 0), 0.0)

    def test_41_teacher_enters_marks_and_student_sees_percentage(self):
        self.login("teacher1", "teacher123")
        ids = [r["id"] for r in self.rows("SELECT id FROM students WHERE class_id = 1 ORDER BY id")]
        form = {"ts": 1, "assessment_type": "Quiz", "assessment_name": "Quiz 2", "total_marks": "20"}
        form[f"marks_{ids[0]}"] = "17"
        r = self.client.post("/teacher/marks", data=form, follow_redirects=True)
        self.assertIn(b"Saved marks for 1 student", r.data)
        stu = self.app.test_client()
        self.login("MCA2601", "student123", stu)
        page = stu.get("/student/performance").data.decode()
        self.assertIn("Quiz 2", page)
        self.assertIn("85.0%", page)

    def test_42_marks_validation(self):
        self.login("teacher1", "teacher123")
        sid = self.rows("SELECT id FROM students WHERE class_id = 1 ORDER BY id")[0]["id"]
        r = self.client.post("/teacher/marks", data={"ts": 1, "assessment_type": "Quiz", "assessment_name": "Bad Quiz",
                             "total_marks": "10", f"marks_{sid}": "15"}, follow_redirects=True)
        self.assertIn(b"must be between 0 and 10", r.data)
        self.assertEqual(self.rows("SELECT COUNT(*) n FROM marks WHERE assessment_name = 'Bad Quiz'")[0]["n"], 0)


class TestReports(BaseCase):
    def test_50_csv_export(self):
        self.login("admin", "admin123")
        r = self.client.get("/admin/reports?export=csv&subject_id=1")
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/csv", r.headers["Content-Type"])
        self.assertIn("attachment", r.headers["Content-Disposition"])
        rows = list(csv.reader(io.StringIO(r.data.decode("utf-8-sig"))))
        self.assertEqual(rows[0], ["Student Name", "Student ID", "Class", "Subject", "Total Classes", "Present", "Absent", "Attendance %"])
        self.assertEqual(len(rows) - 1, 20)                            # 20 students x 1 subject
        first = rows[1]
        self.assertEqual(round(int(first[5]) * 100 / int(first[4]), 2), float(first[7]))

    def test_51_report_filters_date_range(self):
        self.login("admin", "admin123")
        r = self.client.get("/admin/reports?export=csv&from_date=2026-07-01&to_date=2026-07-31&student_id=1&subject_id=1")
        rows = list(csv.reader(io.StringIO(r.data.decode("utf-8-sig"))))
        self.assertEqual(len(rows), 2)
        total = self.rows("SELECT COUNT(*) n FROM attendance WHERE student_id=1 AND subject_id=1 "
                          "AND attendance_date BETWEEN '2026-07-01' AND '2026-07-31'")[0]["n"]
        self.assertEqual(int(rows[1][4]), total)

    def test_52_teacher_report_limited_to_own_subjects(self):
        self.login("teacher1", "teacher123")
        r = self.client.get("/teacher/reports?export=csv")
        text = r.data.decode("utf-8-sig")
        self.assertIn("PYT101", text)
        self.assertNotIn("DSA104", text)                              # belongs to teacher2

    def test_53_pdf_export(self):
        self.login("admin", "admin123")
        r = self.client.get("/admin/reports?export=pdf")
        self.assertEqual(r.headers["Content-Type"], "application/pdf")
        self.assertTrue(r.data.startswith(b"%PDF"))


class TestAllPagesLoad(BaseCase):
    def test_60_every_page_loads_for_its_role(self):
        pages = {
            ("admin", "admin123"): ["/admin/dashboard", "/admin/students", "/admin/teachers", "/admin/subjects",
                                    "/admin/classes", "/admin/reports", "/admin/settings"],
            ("teacher1", "teacher123"): ["/teacher/dashboard", "/teacher/attendance", "/teacher/attendance/history",
                                         "/teacher/students", "/teacher/marks", "/teacher/reports"],
            ("MCA2601", "student123"): ["/student/dashboard", "/student/attendance", "/student/performance", "/student/profile"],
        }
        for (user, pw), urls in pages.items():
            c = self.app.test_client()
            self.login(user, pw, c)
            for u in urls:
                self.assertEqual(c.get(u).status_code, 200, u)


if __name__ == "__main__":
    unittest.main(verbosity=2)
