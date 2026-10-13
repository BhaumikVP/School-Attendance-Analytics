
import pandas as pd
from io import BytesIO
import database as db

def generate_report_data(class_id=None, start_date=None, end_date=None):
    students = db.get_all_students()
    if class_id:
        students = [s for s in students if s["classID"] == class_id]
    return students  # extend with date-range attendance joins as needed



def generate_excel_report(data):
    df = pd.DataFrame(data)
    buffer = BytesIO()
    df.to_excel(buffer, index=False, engine="openpyxl")
    buffer.seek(0)
    return buffer
