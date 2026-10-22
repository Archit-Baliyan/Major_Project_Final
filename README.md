# Smart Attendance and Analytics System

A web-based system that automates student attendance and shows performance analytics dashboards.
Built as an **MCA minor project** with **Python 3 + Flask + MySQL** (no React / Node / Django / MongoDB).

> This is a rule-based analytics system (percentages, thresholds, trends). It does **not** use AI/ML.

## Project objective
Replace paper attendance registers with a system where teachers mark attendance online, students can see
their own attendance/marks and get warnings, and the admin/teachers get charts and exportable reports.

## Features
| Role | What it can do |
|------|----------------|
| **Admin** | Login/logout; add/edit/delete students, teachers, subjects, classes; assign teachers to subject + class; overall dashboard & analytics; reports (CSV/PDF); configure minimum attendance % |
| **Teacher** | See assigned subjects/classes; mark attendance (Mark All Present/Absent); edit past attendance; attendance history; student list with attendance %; enter marks (Assignment / Internal / Quiz / Exam); dashboard with charts; filtered reports (CSV/PDF) |
| **Student** | Personal dashboard; overall + subject-wise attendance %; present/absent days; attendance history with filters; marks & performance charts; **low-attendance warning**; change password |

Smart features: low attendance warning, students at risk, subject-wise analysis, monthly trend, monthly statistics,
top/lowest attendance students, attendance summary, configurable minimum % (default 75).

Security: PBKDF2 password hashing, session login, role-based access control on every route, parameterised SQL
(SQL-injection safe), server-side validation, CSRF token on every POST, confirmation before deleting.

## Technologies
Python 3, Flask, MySQL, mysql-connector-python, HTML5, CSS3, JavaScript, Bootstrap 5, Bootstrap Icons, Chart.js, ReportLab (PDF), Git.
Bootstrap and Chart.js are stored **locally in `static/vendor/`**, so the app works even without internet.

## System requirements
Windows 10/11 (also works on Linux/macOS) - Python 3.9+ - MySQL Server 8.x (or MariaDB 10.5+) - a modern browser - Git (optional)

## Installation (Windows, step by step)
Open **Command Prompt** inside the project folder (`smart-attendance-system`).

```bat
:: 1. create virtual environment
python -m venv venv

:: 2. activate it
venv\Scripts\activate

:: 3. install requirements
pip install -r requirements.txt

:: 4. create your settings file, then open .env in Notepad and put YOUR MySQL password
copy .env.example .env
notepad .env
```

### Database setup (choose ONE way)
**Way A - easiest (uses Python, no mysql command needed):**
```bat
python database\init_db.py
```
This creates the database `smart_attendance`, all tables and the demo data.

**Way B - with the MySQL command line:**
```bat
mysql -u root -p -e "source database/schema.sql"
mysql -u root -p -e "source database/seed.sql"
```
(`schema.sql` creates the database + tables, `seed.sql` fills demo data. Both **delete existing data** in this project's tables.)

### Run the application
```bat
python app.py
```
Open **http://127.0.0.1:5000** in the browser.

## Run with Docker Compose
Install Docker Desktop, open a terminal in the project folder, then run:

```sh
docker compose up --build
```

Compose starts MySQL, creates the schema and demo data on the first run, then starts the app when MySQL is healthy. Open **http://localhost:5000**. The MySQL data is kept in the `mysql_data` volume when the containers stop.

For local-only use, the Compose file provides development defaults. To override them, create a `.env` file with `DB_PASSWORD`, `MYSQL_ROOT_PASSWORD`, and `SECRET_KEY`; use strong, distinct values for any shared or deployed environment.

Stop the services with `docker compose down`. To delete the database and its demo/user data and initialize from scratch on the next start, run `docker compose down -v`.

### Run the automated tests (optional)
```bat
python -m unittest tests.test_app -v
```
Tests use a separate database `smart_attendance_test`, so your real data is safe.

## Login credentials (LOCAL DEMO ONLY - change them for any real use)
| Role | Username | Password |
|------|----------|----------|
| Admin | `admin` | `admin123` |
| Teacher 1 - Dr. Anita Sharma (PYT101, DBM102, WEB103) | `teacher1` | `teacher123` |
| Teacher 2 - Prof. Vikram Malhotra (DSA104, MAT105) | `teacher2` | `teacher123` |
| Students (20) | `MCA2601` ... `MCA2620` | `student123` |

Good students to demo: `MCA2611` (~97 %, no warning) and `MCA2613` (~55 %, low-attendance warning).

## Demo data (loaded by seed.sql)
1 admin, 2 teachers, 20 students, 5 subjects, 2 classes (MCA Sem-1 A and B, 10 students each), about 3,360 attendance
records (6 Jul - 23 Sep 2026) and 400 marks records. The dashboards are populated immediately.

## Project structure
```
smart-attendance-system/
|-- app.py                  # creates the Flask app, registers blueprints, error pages
|-- config.py               # settings (reads .env)
|-- requirements.txt
|-- .env.example            # copy to .env and add your MySQL password
|-- database/
|   |-- schema.sql          # tables, keys, indexes
|   |-- seed.sql            # demo data
|   |-- init_db.py          # runs schema + seed from Python
|   `-- generate_seed.py    # (optional) regenerates seed.sql
|-- routes/                 # URL handlers (controllers)
|   |-- auth.py  admin.py  teacher.py  student.py
|   `-- shared.py           # report page used by admin + teacher
|-- models/
|   |-- analytics.py        # attendance %, marks %, dashboard queries
|   `-- reports.py          # report query + CSV/PDF export
|-- utils/
|   |-- db.py               # MySQL helper (parameterised queries, transactions)
|   |-- auth.py             # role_required, CSRF, password hashing
|   `-- validators.py       # server-side validation
|-- templates/              # Jinja2 HTML (base, login, dashboard, reports, admin/, teacher/, student/)
|-- static/                 # css/, js/ (app.js, charts.js), vendor/ (Bootstrap, Chart.js), images/
|-- tests/test_app.py       # 29 automated test cases
`-- docs/                   # project report (docx), ER/architecture/DFD diagrams, viva Q&A
```
The teacher/admin dashboard share one template (`templates/dashboard.html`) because they show the same
analytics on different scopes; this is a deliberate simplification of the suggested structure.

## Pages
`/login` - `/admin/dashboard|students|teachers|subjects|classes|reports|settings` -
`/teacher/dashboard|attendance|attendance/history|students|marks|reports` -
`/student/dashboard|attendance|performance|profile`

## How the calculations work
```
Attendance %  = (Present classes / Total classes) x 100      (0 if no classes yet)
Marks %       = (Marks obtained / Total marks) x 100
```
* **Overall attendance of a student** = all Present rows / all attendance rows of that student.
* **Subject-wise** = same formula, grouped by subject (`GROUP BY subject`).
* **Average attendance (dashboard)** = total Present rows / total rows of all students in scope.
* **Students at risk / low attendance warning** = students whose % is below `min_attendance` (settings table, default 75).
* **Monthly trend** = attendance % grouped by month (`LEFT(attendance_date, 7)` -> `2026-08`).
* **Top / lowest students** = students sorted by overall %, first 5 / last 5.
* Teachers see only the (subject, class) pairs assigned to them; admins see everything.
* Every number comes from MySQL queries - nothing is hard-coded.

## Database relationships (short)
* `users` 1-1 `students` / `teachers` (login account -> profile)
* `classes` 1-N `students`
* `teacher_subjects` links teacher + subject + class (unique per subject+class)
* `students` 1-N `attendance`, `subjects` 1-N `attendance`  -> UNIQUE(student, subject, date) stops duplicates
* `students` 1-N `marks`, `subjects` 1-N `marks`
* `settings` holds `min_attendance`
Diagram: `docs/er.png`.

## Design decisions (differences from the suggested schema)
* `subjects.teacher_id` is replaced by the `teacher_subjects` table (a teacher can teach many subjects and a subject can be taught by different teachers in different classes).
* The `student_classes` table is not used; each student has one `class_id` (simpler for a minor project). Use `student_classes` if students must belong to many classes.
* Extra table `settings` stores the configurable minimum attendance.

## Screenshots
_Add your screenshots here after running the project (login, admin dashboard, mark attendance, student dashboard, report)._

| Page | Screenshot |
|------|-----------|
| Login | `docs/screenshots/login.png` |
| Admin dashboard | `docs/screenshots/admin-dashboard.png` |
| Mark attendance | `docs/screenshots/attendance.png` |
| Student dashboard | `docs/screenshots/student-dashboard.png` |

## Troubleshooting
| Problem | Fix |
|---------|-----|
| `Access denied for user 'root'` | Wrong password in `.env` (`DB_PASSWORD`). Test it with `mysql -u root -p`. |
| `Can't connect to MySQL server` / "Database error" page | MySQL service is not running: `net start MySQL80` (Admin CMD) or start it from *Services*. Check `DB_HOST` / `DB_PORT`. |
| `Unknown database 'smart_attendance'` | You skipped the DB setup - run `python database\init_db.py`. |
| `'mysql' is not recognized` | Use Way A (`python database\init_db.py`) or add MySQL's `bin` folder to PATH. |
| `ModuleNotFoundError: No module named 'flask'` | Virtual environment not active. Run `venv\Scripts\activate` and `pip install -r requirements.txt`. |
| PowerShell says running scripts is disabled | Use Command Prompt, or run `Set-ExecutionPolicy -Scope Process RemoteSigned` first. |
| `mysql-connector-python` install fails | Upgrade pip: `python -m pip install --upgrade pip`, then install again. |
| Port 5000 already in use | Change the last line of `app.py` to `app.run(debug=True, port=5001)`. |
| "Invalid or missing CSRF token" | Your session expired - reload the page and try again. |
| Login says invalid password for demo users | You changed the DB name/data - re-run `python database\init_db.py`. |
| Charts are empty | No attendance data yet - run the seed, or mark attendance as a teacher. |

## Limitations
* No email/SMS notifications; no biometric/QR/face-recognition attendance (attendance is marked manually by teachers).
* One attendance mark per student, subject and date (no separate lecture slots on the same day).
* No "forgot password" e-mail flow (admin can reset passwords by editing a user; students can change their own).
* No login rate-limiting/lockout; `app.run(debug=True)` is for local use only - use a production server (Waitress/Gunicorn) to deploy.
* PDF export is a simple table.

## Future enhancements
QR-code or face-recognition attendance - SMS/e-mail alerts for low attendance - period/lecture slots - leave management -
parent portal - attendance prediction using machine learning - Excel import of students - REST API + mobile app.

## Git
```bat
git init
git add .
git commit -m "Smart Attendance and Analytics System - initial version"
```
`.env` is in `.gitignore`, so your password is never committed.
