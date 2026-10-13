"""Attendance statistics.

Status rules used everywhere in the app:
  - Present        -> counts as attended
  - Late           -> counts as attended (the student came, just not on time)
  - Absent         -> counts as not attended
  - Medical Leave  -> excused: left out of the percentage entirely

Every function takes an optional class_id; None means all classes.
"""
import database as db

# SQL fragments so every query applies the same rules.
_ATTENDED = "SUM(a.stat IN ('Present', 'Late'))"
_COUNTED = "NULLIF(SUM(a.stat <> 'Medical Leave'), 0)"
_CLASS_FILTER = "(%s IS NULL OR s.classID = %s)"


def _query(sql, params=()):
    conn = db.get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(sql, params)
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()


def latest_date():
    """Most recent day that has any attendance, or None if the table is empty."""
    return _query("SELECT MAX(date_) AS d FROM attendance")[0]["d"]


def previous_date(day):
    """The most recent recorded day before `day` (skips weekends and holidays)."""
    return _query("SELECT MAX(date_) AS d FROM attendance WHERE date_ < %s", (day,))[0]["d"]


def day_summary(day, class_id=None):
    rows = _query(f"""
        SELECT a.stat, COUNT(*) AS n
        FROM attendance a JOIN students s ON a.studentID = s.studentID
        WHERE a.date_ = %s AND {_CLASS_FILTER}
        GROUP BY a.stat
    """, (day, class_id, class_id))
    counts = {r["stat"]: int(r["n"]) for r in rows}
    total = sum(counts.values())
    attended = counts.get("Present", 0) + counts.get("Late", 0)
    counted = total - counts.get("Medical Leave", 0)
    pct = round(attended / counted * 100, 1) if counted else None
    return {"counts": counts, "total": total, "attended": attended, "pct": pct}


def daily_trend(start, end, class_id=None):
    return _query(f"""
        SELECT a.date_ AS day, ROUND({_ATTENDED} / {_COUNTED} * 100, 2) AS pct
        FROM attendance a JOIN students s ON a.studentID = s.studentID
        WHERE a.date_ BETWEEN %s AND %s AND {_CLASS_FILTER}
        GROUP BY a.date_ ORDER BY a.date_
    """, (start, end, class_id, class_id))


def status_mix(start, end, class_id=None):
    return _query(f"""
        SELECT a.stat, COUNT(*) AS n
        FROM attendance a JOIN students s ON a.studentID = s.studentID
        WHERE a.date_ BETWEEN %s AND %s AND {_CLASS_FILTER}
        GROUP BY a.stat
    """, (start, end, class_id, class_id))


def class_comparison(day):
    return _query(f"""
        SELECT c.classID, c.className, c.division,
               ROUND({_ATTENDED} / {_COUNTED} * 100, 2) AS pct
        FROM attendance a
        JOIN students s ON a.studentID = s.studentID
        JOIN classes c ON s.classID = c.classID
        WHERE a.date_ = %s
        GROUP BY c.classID, c.className, c.division
    """, (day,))


def weekday_pattern(start, end, class_id=None):
    """Attendance % per class per weekday (wd: 0 = Monday)."""
    return _query(f"""
        SELECT c.className, c.division, WEEKDAY(a.date_) AS wd,
               ROUND({_ATTENDED} / {_COUNTED} * 100, 2) AS pct
        FROM attendance a
        JOIN students s ON a.studentID = s.studentID
        JOIN classes c ON s.classID = c.classID
        WHERE a.date_ BETWEEN %s AND %s AND {_CLASS_FILTER}
        GROUP BY c.classID, c.className, c.division, WEEKDAY(a.date_)
    """, (start, end, class_id, class_id))


def watchlist(start, end, class_id=None, limit=8):
    """Students with the lowest attendance % in the period."""
    return _query(f"""
        SELECT s.s_name, s.rollNo, c.className, c.division,
               SUM(a.stat = 'Absent') AS absences,
               ROUND({_ATTENDED} / {_COUNTED} * 100, 1) AS pct
        FROM attendance a
        JOIN students s ON a.studentID = s.studentID
        JOIN classes c ON s.classID = c.classID
        WHERE a.date_ BETWEEN %s AND %s AND {_CLASS_FILTER}
        GROUP BY s.studentID, s.s_name, s.rollNo, c.className, c.division
        HAVING pct IS NOT NULL
        ORDER BY pct ASC, absences DESC
        LIMIT %s
    """, (start, end, class_id, class_id, limit))


def student_attendance_pct(student_id, days=90):
    """Attendance % over the student's most recent `days` records."""
    history = db.get_attendance_history(student_id, days)
    if not history:
        return 0
    counted = [h for h in history if h["stat"] != "Medical Leave"]
    if not counted:
        return 100.0  # only excused days on record, so no evidence of absence
    attended = sum(1 for h in counted if h["stat"] in ("Present", "Late"))
    return round((attended / len(counted)) * 100, 2)
