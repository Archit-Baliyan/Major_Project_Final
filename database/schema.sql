-- =====================================================================
-- Smart Attendance and Analytics System : MySQL schema
-- Run:  mysql -u root -p < database/schema.sql
-- =====================================================================
CREATE DATABASE IF NOT EXISTS smart_attendance CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE smart_attendance;

-- Drop in child -> parent order so the script can be re-run safely
DROP TABLE IF EXISTS marks;
DROP TABLE IF EXISTS attendance;
DROP TABLE IF EXISTS teacher_subjects;
DROP TABLE IF EXISTS students;
DROP TABLE IF EXISTS teachers;
DROP TABLE IF EXISTS subjects;
DROP TABLE IF EXISTS classes;
DROP TABLE IF EXISTS settings;
DROP TABLE IF EXISTS users;

-- Login accounts for all three roles (password is stored only as a hash)
CREATE TABLE users (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    username      VARCHAR(50)  NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role          ENUM('admin','teacher','student') NOT NULL,
    created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- A class = programme + semester + section  (e.g. MCA, 1, A)
CREATE TABLE classes (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    class_name  VARCHAR(50) NOT NULL,
    semester    TINYINT     NOT NULL,
    section     VARCHAR(10) NOT NULL,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_class (class_name, semester, section)
) ENGINE=InnoDB;

CREATE TABLE teachers (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    user_id     INT          NOT NULL UNIQUE,
    teacher_id  VARCHAR(20)  NOT NULL UNIQUE,
    name        VARCHAR(100) NOT NULL,
    email       VARCHAR(120) NOT NULL UNIQUE,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_teacher_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Each student belongs to exactly one class (1 class -> many students)
CREATE TABLE students (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    user_id     INT          NOT NULL UNIQUE,
    student_id  VARCHAR(20)  NOT NULL UNIQUE,
    name        VARCHAR(100) NOT NULL,
    email       VARCHAR(120) NOT NULL UNIQUE,
    class_id    INT          NOT NULL,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_students_class (class_id),
    CONSTRAINT fk_student_user  FOREIGN KEY (user_id)  REFERENCES users(id)   ON DELETE CASCADE,
    CONSTRAINT fk_student_class FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE subjects (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    subject_code  VARCHAR(20)  NOT NULL UNIQUE,
    subject_name  VARCHAR(100) NOT NULL,
    created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- Teacher T teaches subject S to class C  (one teacher per subject per class)
CREATE TABLE teacher_subjects (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    teacher_id  INT NOT NULL,
    subject_id  INT NOT NULL,
    class_id    INT NOT NULL,
    UNIQUE KEY uq_subject_class (subject_id, class_id),
    INDEX idx_ts_teacher (teacher_id),
    CONSTRAINT fk_ts_teacher FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE CASCADE,
    CONSTRAINT fk_ts_subject FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
    CONSTRAINT fk_ts_class   FOREIGN KEY (class_id)   REFERENCES classes(id)  ON DELETE CASCADE
) ENGINE=InnoDB;

-- One row = one student, one subject, one date.
-- The UNIQUE key is what prevents duplicate attendance at database level.
CREATE TABLE attendance (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    student_id       INT  NOT NULL,
    subject_id       INT  NOT NULL,
    attendance_date  DATE NOT NULL,
    status           ENUM('Present','Absent') NOT NULL,
    marked_by        INT NULL,
    created_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_attendance (student_id, subject_id, attendance_date),
    INDEX idx_att_subject_date (subject_id, attendance_date),
    INDEX idx_att_date (attendance_date),
    CONSTRAINT fk_att_student FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    CONSTRAINT fk_att_subject FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
    CONSTRAINT fk_att_teacher FOREIGN KEY (marked_by)  REFERENCES teachers(id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE marks (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    student_id      INT NOT NULL,
    subject_id      INT NOT NULL,
    assessment_type ENUM('Assignment','Internal','Quiz','Exam') NOT NULL,
    assessment_name VARCHAR(100) NOT NULL,
    marks_obtained  DECIMAL(6,2) NOT NULL,
    total_marks     DECIMAL(6,2) NOT NULL,
    entered_by      INT NULL,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_marks (student_id, subject_id, assessment_name),
    INDEX idx_marks_subject (subject_id),
    CONSTRAINT chk_marks CHECK (marks_obtained >= 0 AND marks_obtained <= total_marks),
    CONSTRAINT fk_marks_student FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    CONSTRAINT fk_marks_subject FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
    CONSTRAINT fk_marks_teacher FOREIGN KEY (entered_by) REFERENCES teachers(id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- Key/value settings (used for the configurable minimum attendance %)
CREATE TABLE settings (
    setting_key   VARCHAR(50) PRIMARY KEY,
    setting_value VARCHAR(100) NOT NULL
) ENGINE=InnoDB;
