import os

import bcrypt
import mysql.connector
from dotenv import load_dotenv
from mysql.connector import Error

# Reads DB_* settings from a local .env file (never committed) or the environment.
load_dotenv()


def _db_config():
    password = os.environ.get("DB_PASSWORD")
    if password is None:
        raise RuntimeError(
            "DB_PASSWORD is not set. Copy .env.example to .env and fill in your MySQL credentials"
        )
    return {
        "host": os.environ.get("DB_HOST", "localhost"),
        "user": os.environ.get("DB_USER", "root"),
        "password": password,
        "database": os.environ.get("DB_NAME", "attendance"),
    }


def get_connection():
    try:
        return mysql.connector.connect(**_db_config())
    except Error as e:
        raise RuntimeError("Unable to connect to database") from e


# ---------- CLASSES ----------
def add_class(class_name, division):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO classes (className, division) VALUES (%s, %s)",
        (class_name, division)
    )
    conn.commit()
    cur.close()
    conn.close()

def get_classes():
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM classes ORDER BY className, division")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

# ---------- TEACHERS ----------
def add_teacher(name, email, password, role="Teacher", assigned_class_id=None):
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO teachers (t_name, email, passwordHash, t_role, assigned_classID)
           VALUES (%s, %s, %s, %s, %s)""",
        (name, email, password_hash, role, assigned_class_id)
    )
    conn.commit()
    cur.close()
    conn.close()

def authenticate_teacher(email, password):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM teachers WHERE email = %s", (email,))
    teacher = cur.fetchone()
    cur.close()
    conn.close()
    if teacher and bcrypt.checkpw(password.encode(), teacher["passwordHash"].encode()):
        teacher.pop("passwordHash", None)  # keep the hash out of the session
        return teacher
    return None

# ---------- STUDENTS ----------
def add_student(name, class_id, roll_no, gender, dob, parent_name=None, parent_phone=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO students (s_name, classID, rollNo, gender, dob, parentName, parentPhone)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (name, class_id, roll_no, gender, dob, parent_name, parent_phone)
    )
    conn.commit()
    cur.close()
    conn.close()

_STUDENT_COLUMNS = {"s_name", "classID", "rollNo", "gender", "dob", "parentName", "parentPhone"}

def update_student(student_id, **fields):
    if not fields:
        return
    unknown = set(fields) - _STUDENT_COLUMNS
    if unknown:
        raise ValueError(f"Unknown student column(s): {', '.join(sorted(unknown))}")
    conn = get_connection()
    cur = conn.cursor()
    set_clause = ", ".join(f"{k} = %s" for k in fields)
    values = list(fields.values()) + [student_id]
    cur.execute(f"UPDATE students SET {set_clause} WHERE studentID = %s", values)
    conn.commit()
    cur.close()
    conn.close()

def get_all_students():
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT s.*, c.className, c.division
        FROM students s JOIN classes c ON s.classID = c.classID
        ORDER BY c.className, c.division, s.rollNo
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def get_students_by_class(class_id):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM students WHERE classID = %s ORDER BY rollNo", (class_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

# ---------- ATTENDANCE ----------
def mark_attendance_batch(records, marked_by):
    """records = [(studentID, date_, status, remarks), ...]"""
    conn = get_connection()
    cur = conn.cursor()
    try:
        for student_id, date_, status, remarks in records:
            cur.execute(
                """INSERT INTO attendance (studentID, date_, stat, remarks, markedBy)
                   VALUES (%s, %s, %s, %s, %s)
                   ON DUPLICATE KEY UPDATE stat = VALUES(stat), remarks = VALUES(remarks)""",
                (student_id, date_, status, remarks, marked_by)
            )
        conn.commit()
        return True
    except Error as e:
        conn.rollback()
        print(f"Attendance save failed: {e}")
        return False
    finally:
        cur.close()
        conn.close()

def get_attendance_for_class_date(class_id, date_):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT s.studentID, s.s_name, s.rollNo, a.stat, a.remarks
        FROM students s
        LEFT JOIN attendance a ON s.studentID = a.studentID AND a.date_ = %s
        WHERE s.classID = %s
        ORDER BY s.rollNo
    """, (date_, class_id))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def get_attendance_history(student_id, limit_days=90):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT date_, stat FROM attendance
        WHERE studentID = %s ORDER BY date_ DESC LIMIT %s
    """, (student_id, limit_days))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

# ---------- RISK SCORES ----------
def insert_risk_score(student_id, calc_date, attendance_pct, consecutive, risk_prob, risk_level):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO riskScores (studentID, calculatedDate, attendancepct, consecutive, riskProbability, riskLevel)
           VALUES (%s, %s, %s, %s, %s, %s)
           ON DUPLICATE KEY UPDATE attendancepct=VALUES(attendancepct),
               consecutive=VALUES(consecutive), riskProbability=VALUES(riskProbability),
               riskLevel=VALUES(riskLevel)""",
        (student_id, calc_date, attendance_pct, consecutive, risk_prob, risk_level)
    )
    conn.commit()
    cur.close()
    conn.close()

def get_latest_risk_scores():
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT r.*, s.s_name, s.rollNo, c.className, c.division
        FROM riskScores r
        JOIN students s ON r.studentID = s.studentID
        JOIN classes c ON s.classID = c.classID
        WHERE r.calculatedDate = (SELECT MAX(calculatedDate) FROM riskScores)
        ORDER BY r.riskProbability DESC
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows
