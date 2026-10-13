import altair as alt
import streamlit as st
import pandas as pd
from datetime import date, timedelta
import database as db
import analytics
import prediction
import reports

STATUSES = ["Present", "Absent", "Late", "Medical Leave"]

# Dashboard styling and targets
ACCENT = "#3B82C4"
TARGET_PCT = 90
STATUS_COLORS = {"Present": "#2E9E6B", "Late": "#E0A526", "Absent": "#D64545", "Medical Leave": "#8A94A6"}
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

st.set_page_config(page_title="School Attendance Analytics", layout="wide")
st.markdown("""
<style>
.block-container {
    padding-top: 2rem;
    padding-bottom: 2rem;
}

/* KPI cards - adapt to theme automatically */
div[data-testid="stMetric"] {
    background-color: var(--secondary-background-color);
    border: 1px solid rgba(128, 128, 128, 0.2);
    border-radius: 10px;
    padding: 16px 20px;
}
div[data-testid="stMetricLabel"] {
    font-size: 0.85rem;
    opacity: 0.7;
}
div[data-testid="stMetricValue"] {
    font-size: 1.8rem;
    color: var(--primary-color);
}

/* Buttons */
.stButton > button {
    border-radius: 8px;
    font-weight: 500;
    border: 1px solid var(--primary-color);
}
.stButton > button:hover {
    border-color: var(--primary-color);
    color: var(--primary-color);
}

/* Login heading */
.login-title {
    color: var(--primary-color);
    font-weight: 700;
    margin-bottom: 4px;
    text-align: center;
}
.login-subtitle {
    opacity: 0.65;
    font-size: 0.9rem;
    margin-bottom: 20px;
    text-align: center;
}
</style>
""", unsafe_allow_html=True)

if "teacher" not in st.session_state:
    st.session_state.teacher = None


def login_screen():
    # Each st.markdown call renders as its own block, so a card has to be a real
    # container; a <div> opened in one call and closed in another would not wrap the form.
    st.write("")
    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        with st.container(border=True):
            st.markdown('<div class="login-title" style="font-size:1.6rem;">School Attendance Analytics</div>', unsafe_allow_html=True)
            st.markdown('<div class="login-subtitle">Sign in to your account</div>', unsafe_allow_html=True)
            with st.form("login"):
                email = st.text_input("Email")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Log in", width="stretch")
                if submitted:
                    teacher = db.authenticate_teacher(email.strip(), password)
                    if teacher:
                        st.session_state.teacher = teacher
                        st.rerun()
                    else:
                        st.error("Invalid email or password")


def _fmt_pct(value):
    return "n/a" if value is None else f"{value}%"


def dashboard():
    st.header("Dashboard")
    latest = analytics.latest_date()
    if latest is None:
        st.info("No attendance has been recorded yet. Use Attendance Entry to mark a day.")
        return

    classes = db.get_classes()
    short = {c["classID"]: f"{c['className']}{c['division']}" for c in classes}
    class_map = {"All classes": None,
                 **{f"{c['className']} - {c['division']}": c["classID"] for c in classes}}

    f1, f2, f3 = st.columns(3)
    class_label = f1.selectbox("Class", list(class_map.keys()))
    period = f2.selectbox("Trend period", [7, 14, 30, 60], index=2,
                          format_func=lambda d: f"Last {d} days")
    day = f3.date_input("Report day", value=latest, max_value=latest) or latest
    class_id = class_map[class_label]
    start = day - timedelta(days=period - 1)

    # ---------- KPI cards ----------
    today = analytics.day_summary(day, class_id)
    prev_day = analytics.previous_date(day)
    prev = analytics.day_summary(prev_day, class_id) if prev_day else None

    risk = db.get_latest_risk_scores()
    if class_id is not None:
        risk = [r for r in risk if f"{r['className']}{r['division']}" == short[class_id]]
    high_risk = sum(1 for r in risk if r["riskLevel"] == "High")

    pct_delta = None
    if prev and prev["pct"] is not None and today["pct"] is not None:
        pct_delta = f"{today['pct'] - prev['pct']:+.1f} pts vs previous day"
    absent_now = today["counts"].get("Absent", 0)
    absent_delta = None
    if prev and prev["total"]:
        absent_delta = f"{absent_now - prev['counts'].get('Absent', 0):+d} vs previous day"

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Attendance", _fmt_pct(today["pct"]), pct_delta)
    k2.metric("Attended (incl. Late)", today["attended"])
    k3.metric("Absent", absent_now, absent_delta, delta_color="inverse")
    k4.metric("High-risk students", high_risk)
    st.caption(
        f"Showing {day:%A, %d %b %Y}. Attendance % counts Late as present and leaves out Medical Leave. "
        f"High-risk comes from the latest risk calculation."
    )
    if today["total"] == 0:
        st.info("No attendance was marked on this day for this selection.")

    # ---------- Trend ----------
    st.subheader(f"Attendance trend ({class_label.lower() if class_id is None else class_label})")
    trend = pd.DataFrame(analytics.daily_trend(start, day, class_id))
    if trend.empty:
        st.info("No attendance in this period.")
    else:
        trend["pct"] = pd.to_numeric(trend["pct"])
        trend["day"] = pd.to_datetime(trend["day"])
        trend["avg7"] = trend["pct"].rolling(7, min_periods=1).mean().round(2)
        low = max(0, int(trend["pct"].min() // 5 * 5) - 5)
        base = alt.Chart(trend).encode(x=alt.X("day:T", title=None, axis=alt.Axis(format="%d %b")))
        y = alt.Y("pct:Q", title="Attendance %", scale=alt.Scale(domain=[low, 100]))
        area = base.mark_area(opacity=0.12, color=ACCENT).encode(y=y)
        line = base.mark_line(color=ACCENT, point=alt.OverlayMarkDef(size=45)).encode(
            y=y,
            tooltip=[alt.Tooltip("day:T", title="Date", format="%a %d %b"),
                     alt.Tooltip("pct:Q", title="Attendance %", format=".1f"),
                     alt.Tooltip("avg7:Q", title="7-day avg", format=".1f")],
        )
        avg = base.mark_line(color="#9AA4B2", strokeDash=[5, 4]).encode(y="avg7:Q")
        target = alt.Chart(pd.DataFrame({"y": [TARGET_PCT]})).mark_rule(
            color=STATUS_COLORS["Absent"], strokeDash=[2, 3]).encode(y="y:Q")
        st.altair_chart((area + line + avg + target).properties(height=300))
        st.caption(f"Dashed grey line: 7-day average. Red dotted line: {TARGET_PCT}% target.")

    # ---------- Status mix and class comparison ----------
    left, right = st.columns(2)
    with left:
        st.subheader("Status mix")
        mix = pd.DataFrame(analytics.status_mix(start, day, class_id))
        if mix.empty:
            st.info("No records in this period.")
        else:
            mix["n"] = mix["n"].astype(int)
            donut = alt.Chart(mix).mark_arc(innerRadius=62).encode(
                theta="n:Q",
                color=alt.Color("stat:N", title=None,
                                scale=alt.Scale(domain=list(STATUS_COLORS), range=list(STATUS_COLORS.values())),
                                legend=alt.Legend(orient="bottom")),
                tooltip=[alt.Tooltip("stat:N", title="Status"), alt.Tooltip("n:Q", title="Records")],
            ).properties(height=300)
            st.altair_chart(donut)
    with right:
        st.subheader(f"Class comparison ({day:%d %b})")
        cc = pd.DataFrame(analytics.class_comparison(day))
        if cc.empty:
            st.info("No attendance was marked for any class on this day.")
        else:
            cc["pct"] = pd.to_numeric(cc["pct"])
            cc["Class"] = cc["className"] + cc["division"]
            cc["Target"] = cc["pct"].ge(TARGET_PCT).map({True: "On target", False: "Below target"})
            bars = alt.Chart(cc).mark_bar(cornerRadiusEnd=4).encode(
                y=alt.Y("Class:N", sort="-x", title=None),
                x=alt.X("pct:Q", title="Attendance %", scale=alt.Scale(domain=[0, 100])),
                color=alt.Color("Target:N", title=None,
                                scale=alt.Scale(domain=["On target", "Below target"],
                                                range=[STATUS_COLORS["Present"], STATUS_COLORS["Absent"]]),
                                legend=alt.Legend(orient="bottom")),
                tooltip=[alt.Tooltip("Class:N"), alt.Tooltip("pct:Q", title="Attendance %", format=".1f")],
            )
            labels = alt.Chart(cc).mark_text(align="left", dx=4).encode(
                y=alt.Y("Class:N", sort="-x"), x="pct:Q", text=alt.Text("pct:Q", format=".1f"))
            st.altair_chart((bars + labels).properties(height=300))
            best, worst = cc.loc[cc["pct"].idxmax()], cc.loc[cc["pct"].idxmin()]
            st.caption(f"Highest: {best['Class']} ({best['pct']:.1f}%). Lowest: {worst['Class']} ({worst['pct']:.1f}%).")

    # ---------- Weekday heatmap and watchlist ----------
    left, right = st.columns(2)
    with left:
        st.subheader("Which weekdays are weakest?")
        wd = pd.DataFrame(analytics.weekday_pattern(start, day, class_id))
        if wd.empty:
            st.info("No records in this period.")
        else:
            wd["pct"] = pd.to_numeric(wd["pct"])
            wd["Class"] = wd["className"] + wd["division"]
            wd["Weekday"] = wd["wd"].astype(int).map(lambda i: WEEKDAYS[i])
            heat = alt.Chart(wd).encode(
                x=alt.X("Weekday:N", sort=WEEKDAYS, title=None, axis=alt.Axis(labelAngle=0)),
                y=alt.Y("Class:N", title=None),
            )
            cells = heat.mark_rect(cornerRadius=3).encode(
                color=alt.Color("pct:Q", title="Attendance %", scale=alt.Scale(scheme="blues", domain=[80, 100], clamp=True)),
                tooltip=[alt.Tooltip("Class:N"), alt.Tooltip("Weekday:N"),
                         alt.Tooltip("pct:Q", title="Attendance %", format=".1f")],
            )
            text = heat.mark_text(fontSize=11).encode(
                text=alt.Text("pct:Q", format=".0f"),
                color=alt.condition(alt.datum.pct > 94, alt.value("white"), alt.value("black")),
            )
            st.altair_chart((cells + text).properties(height=max(120, 48 * wd["Class"].nunique())))
            st.caption("Darker means higher attendance.")
    with right:
        st.subheader("Needs attention")
        wl = pd.DataFrame(analytics.watchlist(start, day, class_id))
        if wl.empty:
            st.info("No records in this period.")
        else:
            wl["Class"] = wl["className"] + wl["division"]
            wl["pct"] = pd.to_numeric(wl["pct"])
            wl["absences"] = wl["absences"].astype(int)
            table = wl[["rollNo", "s_name", "Class", "absences", "pct"]].rename(columns={
                "rollNo": "Roll", "s_name": "Student", "absences": "Absences", "pct": "Attendance %"})
            st.dataframe(
                table, hide_index=True, width="stretch",
                column_config={"Attendance %": st.column_config.ProgressColumn(
                    "Attendance %", min_value=0, max_value=100, format="%.1f%%")},
            )
            st.caption(f"Lowest attendance in the last {period} days.")


def student_management():
    st.header("Student Management")
    flash = st.session_state.pop("flash", None)
    if flash:
        st.success(flash)

    students = db.get_all_students()
    st.dataframe(pd.DataFrame(students), width="stretch")

    classes = db.get_classes()
    class_map = {f"{c['className']} - {c['division']}": c["classID"] for c in classes}
    with st.expander("Add Student"):
        if not class_map:
            st.info("Add a class first.")
            return
        with st.form("add_student"):
            name = st.text_input("Name")
            class_label = st.selectbox("Class", list(class_map.keys()))
            roll_no = st.text_input("Roll No")
            gender = st.selectbox("Gender", ["Male", "Female"])
            dob = st.date_input(
                "Date of Birth",
                value=date(2012, 1, 1),
                min_value=date(1990, 1, 1),
                max_value=date.today()
            )
            parent_name = st.text_input("Parent Name (optional)")
            parent_phone = st.text_input("Parent Phone (optional)")
            if st.form_submit_button("Save"):
                if not name.strip() or not roll_no.strip():
                    st.error("Name and roll number are required.")
                else:
                    try:
                        db.add_student(
                            name.strip(), class_map[class_label], roll_no.strip(), gender, dob,
                            parent_name.strip() or None, parent_phone.strip() or None
                        )
                    except RuntimeError:
                        raise
                    except Exception:
                        st.error("Could not add the student. Is this roll number already used in that class?")
                    else:
                        st.session_state["flash"] = f"Added {name.strip()}"
                        st.rerun()


def attendance_entry():
    st.header("Attendance Entry")
    classes = db.get_classes()
    if not classes:
        st.info("No classes have been set up yet.")
        return
    class_map = {f"{c['className']} - {c['division']}": c["classID"] for c in classes}
    class_label = st.selectbox("Class", list(class_map.keys()))
    entry_date = st.date_input("Date", value=date.today(), max_value=date.today())
    class_id = class_map[class_label]

    roster = db.get_attendance_for_class_date(class_id, entry_date)
    if not roster:
        st.info("This class has no students yet.")
        return

    statuses = {}
    for s in roster:
        default = s["stat"] or "Present"
        # The key includes class and date so each roster loads its own saved values.
        statuses[s["studentID"]] = st.radio(
            f"{s['rollNo']} - {s['s_name']}",
            STATUSES,
            index=STATUSES.index(default),
            horizontal=True,
            key=f"att_{class_id}_{entry_date.isoformat()}_{s['studentID']}"
        )

    if st.button("Save Attendance"):
        records = [(sid, entry_date, status, None) for sid, status in statuses.items()]
        ok = db.mark_attendance_batch(records, marked_by=st.session_state.teacher["teacherID"])
        if ok:
            st.success("Attendance saved")
        else:
            st.error("Save failed")


def reports_page():
    st.header("Reports")
    classes = db.get_classes()
    class_map = {"All Classes": None, **{f"{c['className']} - {c['division']}": c["classID"] for c in classes}}
    class_label = st.selectbox("Class", list(class_map.keys()))

    if st.button("Generate"):
        data = reports.generate_report_data(class_id=class_map[class_label])
        st.dataframe(pd.DataFrame(data))
        excel_buffer = reports.generate_excel_report(data)
        st.download_button(
            "Download Excel", excel_buffer, file_name="report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )


def risk_alerts():
    st.header("Risk Alerts")
    st.caption(
        "Prototype: scores come from a logistic regression trained on a small synthetic "
        "table, not yet on real outcomes. Use them to demonstrate the approach."
    )
    if st.button("Run Risk Calculation"):
        prediction.run_weekly_risk_calculation()
        st.success("Risk scores updated")
    risk = db.get_latest_risk_scores()
    if not risk:
        st.info("No risk scores yet. Click 'Run Risk Calculation'.")
        return
    df = pd.DataFrame(risk)
    columns = ["className", "division", "rollNo", "s_name", "attendancepct",
               "consecutive", "riskProbability", "riskLevel"]
    st.dataframe(df[[c for c in columns if c in df.columns]], width="stretch")


# ---------- MAIN ----------
def run_app():
    if st.session_state.teacher is None:
        login_screen()
        return

    st.sidebar.write(f"Logged in as {st.session_state.teacher['t_name']} ({st.session_state.teacher['t_role']})")
    pages = {
        "Dashboard": dashboard,
        "Student Management": student_management,
        "Attendance Entry": attendance_entry,
        "Reports": reports_page,
        "Risk Alerts": risk_alerts,
    }
    page = st.sidebar.radio("Navigate", list(pages.keys()))
    if st.sidebar.button("Log out"):
        st.session_state.teacher = None
        st.rerun()
    pages[page]()


try:
    run_app()
except RuntimeError as e:
    st.error(f"{e}. Check that MySQL is running and that your .env settings are correct.")
