"""Creates DEMO data: simulated teachers, classes, students and 45 days of attendance.

All names and attendance records are randomly generated. No real students are used.
"""
import random
from datetime import date, timedelta
import database as db
import prediction

random.seed(42)  # same demo data every time

if db.get_classes():
    raise SystemExit(
        "The database already contains data, so the seed script was not run. "
        "To start over, drop and recreate the database from schema.sql."
    )

# ---------- 1. Teachers (demo accounts) ----------
db.add_teacher("Bhaumik Panjabi", "admin@school.com", "admin123", role="Administrator")
db.add_teacher("Priya Sharma", "priya.sharma@school.com", "teacher123", role="Teacher")
db.add_teacher("Rohan Mehta", "rohan.mehta@school.com", "teacher123", role="Teacher")

# ---------- 2. Classes ----------
class_defs = [("9", "A"), ("9", "B"), ("10", "B"), ("10", "C"), ("10", "D"),]
for cname, div in class_defs:
    db.add_class(cname, div)

classes = db.get_classes()
class_ids = {f"{c['className']}{c['division']}": c["classID"] for c in classes}

# ---------- 3. Students ----------
first_names = ["Aarav", "Vivaan", "Aditya", "Ishaan", "Kabir", "Ananya", "Diya",
               "Myra", "Saanvi", "Anika", "Reyansh", "Arjun", "Kiara", "Riya",
               "Advait", "Sai", "Vihaan", "Pari", "Zara", "Neha"]
last_names = ["Sharma", "Verma", "Gupta", "Iyer", "Nair", "Reddy", "Joshi",
              "Kapoor", "Malhotra", "Menon", "Rao", "Chatterjee", "Bhatt", "Desai"]

students_by_class = {}
for label, cid in class_ids.items():
    students_by_class[cid] = []
    for roll in range(1, 16):  # 15 students per class
        name = f"{random.choice(first_names)} {random.choice(last_names)}"
        gender = random.choice(["Male", "Female"])
        dob = date(2010, random.randint(1, 12), random.randint(1, 28))
        db.add_student(name, cid, str(roll), gender, dob,
                        parent_name=f"Parent of {name}", parent_phone="9876543210")
        students_by_class[cid].append(roll)

all_students = db.get_all_students()

# ---------- 4. Attendance history (last 45 days, weekdays only) ----------
# Pick roughly 10% of students to be "at-risk" with poor attendance
at_risk_students = random.sample(all_students, k=max(1, len(all_students) // 10))
at_risk_ids = {s["studentID"] for s in at_risk_students}

today = date.today()
records = []
for i in range(45):
    day = today - timedelta(days=i)
    if day.weekday() >= 5:  # skip weekends
        continue
    for s in all_students:
        if s["studentID"] in at_risk_ids:
            status = random.choices(
                ["Present", "Absent", "Late", "Medical Leave"],
                weights=[45, 40, 10, 5]
            )[0]
        else:
            status = random.choices(
                ["Present", "Absent", "Late", "Medical Leave"],
                weights=[88, 5, 5, 2]
            )[0]
        records.append((s["studentID"], day, status, None))

db.mark_attendance_batch(records, marked_by=1)

# ---------- 5. Run risk calculation so the Risk Alerts screen has data ----------
prediction.run_weekly_risk_calculation()

print("Seed data created successfully.")
print(f"{len(all_students)} students, {len(class_defs)} classes, 45 days of attendance (weekdays only).")
print(f"{len(at_risk_ids)} students seeded with poor attendance for the risk demo.")
