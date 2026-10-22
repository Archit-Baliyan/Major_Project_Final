# Viva Guide - Smart Attendance and Analytics System

## 1. Important files (what to say if the examiner opens a file)
| File | Purpose (one line) |
|------|--------------------|
| `app.py` | Creates the Flask app, registers the 4 blueprints, adds CSRF check and error pages |
| `config.py` / `.env` | Database credentials and secret key (kept out of Git) |
| `utils/db.py` | Opens one MySQL connection per request; `query()` and `execute()` always use `%s` placeholders |
| `utils/auth.py` | `role_required` decorator (RBAC), CSRF token, password hashing |
| `utils/validators.py` | Server-side checks (email, IDs, dates) |
| `routes/auth.py` | Login (check hash, create session) and logout |
| `routes/admin.py` | CRUD for students/teachers/subjects/classes, teacher assignment, settings |
| `routes/teacher.py` | Mark/edit attendance, history, students, marks |
| `routes/student.py` | Student dashboard, attendance, performance, profile |
| `models/analytics.py` | Attendance % and marks % formulas + all dashboard SQL |
| `models/reports.py` | Report query with filters + CSV/PDF export |
| `database/schema.sql` | Tables, primary/foreign keys, unique constraints, indexes |
| `database/seed.sql` | Demo data |
| `templates/base.html` | Layout: top navbar, sidebar, flash messages |
| `static/js/charts.js` | Chart.js functions (doughnut, bar, line, pie) |
| `tests/test_app.py` | 29 automated test cases |

## 2. Database relationships
* **users -> students / teachers (1:1)**: `users` holds login data, the profile table holds personal data.
* **classes -> students (1:N)**: a class has many students; a student is in one class.
* **teachers, subjects, classes -> teacher_subjects (N:M:N link table)**: "Teacher T teaches subject S to class C".
* **students -> attendance (1:N)** and **subjects -> attendance (1:N)**: one row per student per subject per date.
  `UNIQUE(student_id, subject_id, attendance_date)` = no duplicates.
* **students -> marks (1:N)**, **subjects -> marks (1:N)**.
* `ON DELETE CASCADE` removes a student's attendance/marks when the student is deleted; `ON DELETE RESTRICT` stops deleting a class that still has students.

## 3. Attendance calculation
`Attendance % = (Present classes / Total classes) x 100`.
Example: 45 present out of 60 classes -> 45/60 x 100 = **75 %**. In SQL: `SUM(status='Present')` / `COUNT(*)`.
Subject-wise uses `GROUP BY subject`; monthly trend uses `GROUP BY LEFT(attendance_date, 7)`.
If total = 0 the app shows 0 % (avoids division by zero).

## 4. Common viva questions and answers
**Q1. What is your project about?**
A web application in Flask + MySQL where teachers mark attendance online; students see their attendance, marks and warnings; admin/teachers see analytics dashboards and export reports.

**Q2. Why Flask and not Django?**
Flask is lightweight and easy to understand: routes, templates and SQL are all visible, which suits a minor project. Django hides a lot behind its ORM/admin.

**Q3. Explain the architecture.**
Three layers: browser (HTML/CSS/JS/Chart.js) -> Flask application (routes, utils, models) -> MySQL. It follows a simple MVC-like split: templates = view, routes = controller, models/analytics = data logic. (See `docs/arch.png`.)

**Q4. How does login work?**
The form posts username/password. The server fetches the user with a parameterised query, verifies the password with `check_password_hash`, and stores `user_id`, `role`, `name`, `profile_id` in the Flask session (a signed cookie). `session.clear()` is called first to avoid session fixation.

**Q5. How are passwords stored?**
Only as salted PBKDF2-SHA256 hashes (Werkzeug `generate_password_hash`). Even the admin cannot see the original password.

**Q6. What is role-based access control?**
Every blueprint has a `before_request` hook using `@role_required("admin")` etc. A student opening `/admin/...` gets **403**; a person who is not logged in is redirected to `/login`. Teachers are also restricted to their own subject-class pairs inside the queries.

**Q7. How do you prevent SQL injection?**
All queries use placeholders (`WHERE username = %s`) and pass values separately to `mysql-connector-python`; user input is never concatenated into SQL. Test `test_03` tries `' OR '1'='1`.

**Q8. What is CSRF and how did you handle it?**
Cross-Site Request Forgery makes a logged-in user's browser submit a request they did not intend. Every form contains a hidden random token stored in the session; the `before_request` hook rejects any POST whose token does not match (400).

**Q9. How do you prevent duplicate attendance?**
Two levels: (1) database `UNIQUE KEY (student_id, subject_id, attendance_date)`; (2) the save uses `INSERT ... ON DUPLICATE KEY UPDATE`, so saving the same date again *edits* the old rows instead of creating new ones.

**Q10. How does a teacher edit old attendance?**
On the attendance page choose the same subject/class/date (or click *View / Edit* in History). The existing status is pre-selected; after saving, the rows are updated.

**Q11. Why a separate `teacher_subjects` table?**
Because it is a many-to-many relationship (one teacher teaches many subjects/classes; a subject can be taught in many classes). Storing `teacher_id` inside `subjects` would allow only one teacher per subject.

**Q12. What is normalization? Is your DB normalized?**
Normalization removes redundancy. Names/emails are stored once (students/teachers), attendance stores only IDs, class info is in `classes`, subject info in `subjects` - so it is in 3NF. The percentage is never stored; it is calculated when needed.

**Q13. Why not store the attendance percentage in the table?**
It would become out of date each time attendance changes (redundant/derived data). Calculating from raw records is always correct.

**Q14. What are primary key, foreign key, unique key and index?**
PK uniquely identifies a row; FK links to another table's PK; UNIQUE prevents duplicate values; an index speeds up searches (e.g. index on `attendance(subject_id, attendance_date)`).

**Q15. What does `ON DELETE CASCADE` do?**
Deleting the parent row automatically deletes child rows (deleting a student deletes attendance + marks).

**Q16. How are the dashboard charts created?**
Flask runs SQL, passes the result to the template as JSON (`|tojson`), and `charts.js` feeds it to Chart.js (doughnut, bar, line, pie, horizontal bar). No numbers are hard-coded.

**Q17. How is the low attendance warning generated?**
`min_attendance` is stored in the `settings` table (default 75, editable by admin). If a student's % < minimum, the student dashboard shows a red warning and the student appears in the "Students at Risk" table.

**Q18. Is this AI?**
No. It is rule-based analytics (formulas, thresholds, trends). AI/ML prediction is listed under future scope.

**Q19. How does CSV export work?**
The report route runs the same filtered query and, when `export=csv`, writes rows with Python's `csv` module into a response with header `Content-Disposition: attachment`. PDF uses ReportLab.

**Q20. What is a session? What is a Flask Blueprint?**
A session stores per-user data between requests (signed cookie). A Blueprint groups related routes (`admin`, `teacher`, `student`, `auth`) into modules.

**Q21. What is Jinja2?**
Flask's template engine: `{{ value }}` prints data, `{% for %}` / `{% if %}` add logic, `{% extends %}` reuses the base layout.

**Q22. How did you test the project?**
29 automated `unittest` cases (login, invalid login, role authorization, add student/subject, mark attendance, duplicate prevention, calculation, low-attendance warning, marks calculation, CSV/PDF export) plus manual testing. Run: `python -m unittest tests.test_app -v`.

**Q23. What are the limitations?**
Manual marking only (no QR/biometric), no e-mail/SMS alerts, one mark per student/subject/day, no rate limiting, development server only.

**Q24. How would you deploy it?**
Use a production WSGI server (Waitress on Windows / Gunicorn on Linux), set a strong `SECRET_KEY`, turn off debug, use HTTPS and a dedicated MySQL user instead of root.

**Q25. What would you add next?**
QR-code attendance, SMS/e-mail alerts, ML model to predict at-risk students, leave management, parent portal.

## 5. Troubleshooting
See the table in `README.md` (MySQL not running, wrong password, module not found, port already in use, CSRF error).
