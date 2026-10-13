"""At-risk prediction (PROTOTYPE).

Each student gets two features computed from their recent attendance:
  1. attendance percentage (Late counts as attended, Medical Leave excluded)
  2. longest run of consecutive Absent days

A logistic regression (scikit-learn) turns those into a risk probability.

IMPORTANT: the model is trained on a tiny hand-made synthetic table (see
_prototype_model), not on real student outcomes. It demonstrates the pipeline
end to end. Once a school has months of real attendance plus a labelled outcome
(for example "became chronically absent"), only _prototype_model needs to be
replaced with a model trained on that data.
"""
from datetime import date
import numpy as np
from sklearn.linear_model import LogisticRegression
import database as db
import analytics

HIGH_THRESHOLD = 0.6
MEDIUM_THRESHOLD = 0.3


def compute_features(student_id):
    history = db.get_attendance_history(student_id, limit_days=60)
    if not history:
        return None
    history_sorted = sorted(history, key=lambda h: h["date_"])
    attendance_pct = analytics.student_attendance_pct(student_id, days=60)

    consecutive = 0
    max_consecutive = 0
    for h in history_sorted:
        if h["stat"] == "Absent":
            consecutive += 1
            max_consecutive = max(max_consecutive, consecutive)
        else:
            consecutive = 0

    return {"attendance_pct": attendance_pct, "consecutive_absences": max_consecutive}

def _prototype_model():
    # Prototype: trained on synthetic [attendance_pct, consecutive_absences] -> at_risk
    # examples until real historical data accumulates.
    X = np.array([[95, 0], [90, 1], [80, 2], [70, 3], [60, 5], [50, 7], [40, 8]])
    y = np.array([0, 0, 0, 1, 1, 1, 1])
    model = LogisticRegression()
    model.fit(X, y)
    return model

def run_weekly_risk_calculation():
    model = _prototype_model()
    students = db.get_all_students()
    today = date.today()
    for s in students:
        features = compute_features(s["studentID"])
        if features is None:
            continue
        X = np.array([[features["attendance_pct"], features["consecutive_absences"]]])
        prob = model.predict_proba(X)[0][1]
        level = "High" if prob >= HIGH_THRESHOLD else "Medium" if prob >= MEDIUM_THRESHOLD else "Low"
        db.insert_risk_score(
            s["studentID"], today,
            features["attendance_pct"], features["consecutive_absences"],
            round(float(prob), 4), level
        )
    return True
