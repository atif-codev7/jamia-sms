import math
import pandas as pd
import requests
import streamlit as st

API_URL = "http://127.0.0.1:8000"

st.set_page_config(
    page_title="Jamia Hamdard CSE — Academic Management System",
    page_icon="🏛️",
    layout="wide",
)

# Custom Styling (Jamia Hamdard Emerald Green #006747 & Gold Accents)
st.markdown(
    """
<style>
    .jamia-banner {
        background: linear-gradient(135deg, #006747 0%, #004d35 100%);
        color: white;
        padding: 1.2rem 1.6rem;
        border-radius: 10px;
        margin-bottom: 1.2rem;
        border-left: 7px solid #C5A059;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    }
    .jamia-banner h1 {
        color: white;
        margin: 0;
        font-size: 1.65rem;
        font-weight: 700;
    }
    .jamia-banner p {
        color: #e0f2eb;
        margin: 0.3rem 0 0 0;
        font-size: 0.92rem;
    }
    .metric-box {
        background: #fdfdfd;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 0.9rem;
        text-align: center;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    .badge-eligible {
        display: inline-block;
        background-color: #d1e7dd;
        color: #0f5132;
        padding: 0.25rem 0.65rem;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.85rem;
        border: 1px solid #badbcc;
    }
    .badge-shortage {
        display: inline-block;
        background-color: #f8d7da;
        color: #842029;
        padding: 0.25rem 0.65rem;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.85rem;
        border: 1px solid #f5c2c7;
    }
    .admit-card-unlocked {
        border: 2px dashed #006747;
        background: #fbfdfb;
        border-radius: 12px;
        padding: 1.5rem;
        margin-top: 1rem;
        box-shadow: 0 4px 12px rgba(0,103,71,0.06);
    }
    .admit-card-locked {
        border: 2px solid #dc3545;
        background: #fff8f8;
        border-radius: 12px;
        padding: 1.5rem;
        margin-top: 1rem;
        box-shadow: 0 4px 12px rgba(220,53,69,0.08);
    }
</style>
""",
    unsafe_allow_html=True,
)

# Header Banner
st.markdown(
    """
<div class="jamia-banner">
    <h1>🏛️ JAMIA HAMDARD — DEPARTMENT OF COMPUTER SCIENCE & ENGINEERING</h1>
    <p>Academic Record, Result & Attendance Management System (Project-II: BTCSE 701 | B.Tech CSE 7th Sem)</p>
</div>
""",
    unsafe_allow_html=True,
)

if "auth" not in st.session_state:
    st.session_state.auth = None

# Sidebar Authentication & 1-Click Viva Demo Logins
with st.sidebar:
    st.markdown("### 🏛️ Portal Authentication")
    if st.session_state.auth:
        st.success(
            f"👤 Logged in: **{st.session_state.auth['username']}**\n\n"
            f"Role: **{st.session_state.auth['role'].upper()}**"
        )
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.auth = None
            st.session_state.chat_messages = []
            st.rerun()
    else:
        st.markdown("#### ⚡ 1-Click Viva Demo Login")
        st.caption("One-touch authentication without typing passwords:")

        if st.button("👨‍🏫 Faculty (Ms. Gautami Tripathi)", use_container_width=True):
            r = requests.post(
                f"{API_URL}/auth/login",
                json={"username": "faculty", "password": "faculty123"},
            )
            if r.status_code == 200:
                st.session_state.auth = r.json()
                st.rerun()

        if st.button("🎓 Aarav Sharma (Eligible Student)", use_container_width=True):
            r = requests.post(
                f"{API_URL}/auth/login",
                json={"username": "aarav", "password": "student123"},
            )
            if r.status_code == 200:
                st.session_state.auth = r.json()
                st.rerun()

        if st.button("⚠️ Diya Patel (Shortage / Debarred)", use_container_width=True):
            r = requests.post(
                f"{API_URL}/auth/login",
                json={"username": "diya", "password": "student123"},
            )
            if r.status_code == 200:
                st.session_state.auth = r.json()
                st.rerun()

        if st.button("🆕 Rohan Verma (New Student)", use_container_width=True):
            r = requests.post(
                f"{API_URL}/auth/login",
                json={"username": "rohan", "password": "student123"},
            )
            if r.status_code == 200:
                st.session_state.auth = r.json()
                st.rerun()

        st.divider()
        st.info(
            "**Manual Credentials:**\n"
            "- Faculty: `faculty` / `faculty123`\n"
            "- Students: `aarav` / `diya` / `rohan` (`student123`)"
        )


# =====================================================================
# SCREEN 1: MANUAL LOGIN VIEW (When not logged in)
# =====================================================================
if not st.session_state.auth:
    st.subheader("Sign In with Credentials")
    with st.form("manual_login_form"):
        username = st.text_input("Username (e.g., faculty, aarav, diya)")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Sign In")

        if submit:
            try:
                res = requests.post(
                    f"{API_URL}/auth/login",
                    json={"username": username, "password": password},
                )
                if res.status_code == 200:
                    st.session_state.auth = res.json()
                    st.rerun()
                else:
                    st.error(res.json().get("detail", "Login failed. Check credentials."))
            except requests.exceptions.ConnectionError:
                st.error("Cannot connect to FastAPI backend. Ensure uvicorn is running on port 8000.")


# =====================================================================
# SCREEN 2: STUDENT DASHBOARD
# =====================================================================
elif st.session_state.auth["role"] == "student":
    headers = {"Authorization": f"Bearer {st.session_state.auth['access_token']}"}
    res = requests.get(f"{API_URL}/me/scorecard", headers=headers)

    if res.status_code != 200:
        st.error(res.json().get("detail", "Could not load personal scorecard."))
    else:
        data = res.json()
        st_info = data["student"]

        # Student KPI Banner
        st.markdown(
            f"### Welcome, **{st_info['name']}** (`{st_info['enrollment_no']}`) — Semester {st_info['semester']}"
        )
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Semester Credits", data["total_credits_enrolled"])
        c2.metric("Calculated SGPA", f"{data['sgpa']:.2f}")
        att_val = (
            f"{data['overall_attendance_percentage']}%"
            if data["overall_attendance_percentage"] is not None
            else "Unavailable"
        )
        c3.metric("Overall Attendance", att_val)

        is_eligible = data["overall_attendance_eligibility"] == "Eligible"
        status_html = (
            '<span class="badge-eligible">🟢 ELIGIBLE FOR EXAMS</span>'
            if is_eligible
            else '<span class="badge-shortage">🔴 ATTENDANCE SHORTAGE</span>'
        )
        c4.markdown(f"**Exam Status:**<br>{status_html}", unsafe_allow_html=True)

        st.divider()

        # Student Sub-Tabs
        s_tab1, s_tab2, s_tab3, s_tab4, s_tab5, s_tab6 = st.tabs(
            [
                "📊 Academic Scorecard",
                "🧮 Attendance Recovery Calculator",
                "🎟️ Digital Exam Admit Card",
                "📋 Digital No-Dues Clearance",
                "📝 Re-Evaluation Request",
                "💬 AI Academic Assistant",
            ]
        )

        # SUB-TAB 1: Academic Scorecard Table & Grade Sheet Download
        with s_tab1:
            st.subheader("Semester 7 Grade & Attendance Sheet")
            if data["enrollments"]:
                df = pd.DataFrame(data["enrollments"])[
                    [
                        "course_code",
                        "course_title",
                        "credits",
                        "internal_marks",
                        "max_internal",
                        "external_marks",
                        "max_external",
                        "total_marks",
                        "percentage",
                        "grade",
                        "grade_points",
                        "classes_attended",
                        "classes_held",
                        "attendance_percentage",
                        "attendance_eligibility",
                    ]
                ]
                st.dataframe(df, use_container_width=True)

                col_dl1, col_dl2 = st.columns([1, 3])
                with col_dl1:
                    csv_data = df.to_csv(index=False).encode("utf-8")
                    st.download_button(
                        label="📥 Download Grade Sheet (CSV)",
                        data=csv_data,
                        file_name=f"Jamia_GradeSheet_{st_info['enrollment_no']}.csv",
                        mime="text/csv",
                        use_container_width=True,
                    )
            else:
                st.info("No course enrollments found for this semester.")
            st.caption(f"📌 {data['grading_note']}")

        # SUB-TAB 2: Attendance Recovery Calculator (What-If Simulator)
        with s_tab2:
            st.subheader("🧮 'What-If' Attendance Recovery Simulator")
            st.caption(
                "Calculates consecutive lectures required to satisfy Jamia Hamdard Ordinance 15 (75% Attendance Gate)."
            )

            rec_res = requests.get(f"{API_URL}/me/recovery-calculator", headers=headers)
            if rec_res.status_code == 200:
                rec_data = rec_res.json()
                if rec_data["overall_attendance_eligibility"] == "Shortage":
                    st.error(
                        f"🚨 **Attention Required:** Your overall attendance is **{rec_data['overall_attendance_percentage']}%** "
                        f"(Below mandatory 75.0%). You must attend **{rec_data['overall_consecutive_needed']} consecutive lectures** to be eligible!"
                    )
                else:
                    st.success(
                        f"✅ **Safe Standing:** Your overall attendance is **{rec_data['overall_attendance_percentage']}%**. "
                        f"You have a buffer of **{rec_data['overall_buffer_can_miss']} lectures** you can afford to miss without debarment."
                    )

                st.markdown("#### Subject-Wise Recovery Blueprint")
                rec_rows = []
                for c in rec_data["courses"]:
                    rec_rows.append({
                        "Course Code": c["course_code"],
                        "Title": c["course_title"],
                        "Attended / Held": f"{c['classes_attended']} / {c['classes_held']}",
                        "Attendance %": f"{c['current_percentage']}%" if c["current_percentage"] is not None else "N/A",
                        "Status": c["status"],
                        "Consecutive Needed": c["consecutive_classes_needed"],
                        "Safe Buffer": c["buffer_classes_can_miss"],
                        "Action Plan": c["actionable_message"],
                    })
                st.dataframe(pd.DataFrame(rec_rows), use_container_width=True)

                # Interactive Slider What-If Simulator
                st.markdown("#### 🔬 Interactive What-If Simulator")
                sim_lectures = st.slider(
                    "Simulate attending additional consecutive lectures in all subjects:",
                    min_value=0,
                    max_value=30,
                    value=5,
                    step=1,
                )
                tot_h = data["overall_classes_held"] + sim_lectures
                tot_a = data["overall_classes_attended"] + sim_lectures
                new_pct = round((tot_a / tot_h) * 100.0, 2) if tot_h > 0 else 0.0

                sim_color = "🟢" if new_pct >= 75.0 else "🔴"
                st.info(
                    f"{sim_color} If you attend the next **{sim_lectures} lectures**, your attendance will rise from "
                    f"**{data['overall_attendance_percentage']}%** to **{new_pct}%** "
                    f"({'Eligible for Exams' if new_pct >= 75.0 else 'Still in Shortage'})."
                )

        # SUB-TAB 3: Digital Exam Admit Card with Debarment Gate
        with s_tab3:
            st.subheader("🎟️ Digital Examination Admit Card (Hall Ticket)")
            admit_res = requests.get(f"{API_URL}/me/admit-card", headers=headers)
            if admit_res.status_code == 200:
                admit = admit_res.json()
                if admit["is_eligible"]:
                    st.markdown(
                        f"""
                    <div class="admit-card-unlocked">
                        <div style="text-align: center; border-bottom: 2px solid #006747; padding-bottom: 0.8rem; margin-bottom: 1rem;">
                            <h2 style="color: #006747; margin:0;">JAMIA HAMDARD</h2>
                            <p style="margin: 0.2rem 0; font-weight: 600;">Office of the Controller of Examinations — New Delhi 110062</p>
                            <h4 style="margin: 0.4rem 0 0 0; color: #333;">END-TERM EXAMINATION ADMIT CARD (SEMESTER 7)</h4>
                        </div>
                        <div style="display: flex; justify-content: space-between; margin-bottom: 1rem;">
                            <div>
                                <p><strong>Candidate Name:</strong> {admit['student_name']}</p>
                                <p><strong>Enrollment Number:</strong> {admit['enrollment_no']}</p>
                                <p><strong>Semester / Degree:</strong> 7th Semester | B.Tech CSE</p>
                            </div>
                            <div style="text-align: right;">
                                <p><strong>Hall Ticket No:</strong> <code>{admit['hall_ticket_no']}</code></p>
                                <p><strong>Attendance Standing:</strong> <span class="badge-eligible">75%+ Cleared ({admit['overall_attendance_percentage']}%)</span></p>
                                <p><strong>Issued At:</strong> {admit['issued_at']}</p>
                            </div>
                        </div>
                        <p><strong>Examination Center:</strong> {admit['exam_center']}</p>
                        <p style="font-size: 0.85rem; color: #555;"><strong>Digital Verification Hash:</strong> <code>{admit['qr_verification_hash']}</code></p>
                    </div>
                    """,
                        unsafe_allow_html=True,
                    )
                    st.markdown("#### Timetable & Exam Venues")
                    sched_df = pd.DataFrame(admit["enrolled_courses"])
                    st.dataframe(sched_df, use_container_width=True)
                    st.download_button(
                        label="🖨️ Download Official Admit Card (HTML)",
                        data=f"<html><body><h1>Jamia Hamdard Hall Ticket</h1><p>Student: {admit['student_name']}</p><p>Enrollment: {admit['enrollment_no']}</p><p>Status: VERIFIED & CLEARED</p></body></html>",
                        file_name=f"AdmitCard_{admit['enrollment_no']}.html",
                        mime="text/html",
                        use_container_width=True,
                    )
                else:
                    st.markdown(
                        f"""
                    <div class="admit-card-locked">
                        <h2 style="color: #dc3545; margin-top:0;">⛔ ADMIT CARD WITHHELD — ATTENDANCE SHORTAGE</h2>
                        <p style="font-size: 1.1rem; color: #721c24;">
                            <strong>Debarment Notice under Jamia Hamdard Academic Ordinance 15:</strong>
                        </p>
                        <p>{admit['debarment_reason']}</p>
                        <hr style="border-color: #f5c2c7;">
                        <p><strong>Hall Ticket Status:</strong> <code>{admit['hall_ticket_no']}</code></p>
                        <p><strong>Immediate Action:</strong> Please report to the Office of Head of Department (HOD) CSE, School of Engineering Sciences & Technology to submit attendance undertakings or verified medical exemption slips.</p>
                    </div>
                    """,
                        unsafe_allow_html=True,
                    )

        # SUB-TAB 4: Digital No-Dues Clearance Status
        with s_tab4:
            st.subheader("📋 Digital 'No-Dues' Clearance Matrix")
            st.caption("Replaces physical paper signature rounds across university departments.")
            nd_res = requests.get(f"{API_URL}/me/no-dues", headers=headers)
            if nd_res.status_code == 200:
                nd = nd_res.json()
                n1, n2 = st.columns(2)
                with n1:
                    st.markdown(
                        f"**📚 Central & Departmental Library:** "
                        f"{'🟢 Cleared' if nd['library']['cleared'] else '🔴 Pending'}<br>"
                        f"<small>{nd['library']['details']}</small>",
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        f"**💳 Finance & Accounts:** "
                        f"{'🟢 Cleared' if nd['accounts']['cleared'] else '🔴 Pending'}<br>"
                        f"<small>{nd['accounts']['details']}</small>",
                        unsafe_allow_html=True,
                    )
                with n2:
                    st.markdown(
                        f"**💻 CSE Practical Labs:** "
                        f"{'🟢 Cleared' if nd['labs']['cleared'] else '🔴 Withheld'}<br>"
                        f"<small>{nd['labs']['details']}</small>",
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        f"**🏢 Proctorial & Hostel Office:** "
                        f"{'🟢 Cleared' if nd['proctor']['cleared'] else '🔴 Pending'}<br>"
                        f"<small>{nd['proctor']['details']}</small>",
                        unsafe_allow_html=True,
                    )
                st.divider()
                if nd["is_all_cleared"]:
                    st.success("✅ All 4 departmental clearances verified. No pending liabilities.")
                else:
                    st.warning("⚠️ Clearance hold active. Resolve practical attendance shortage to complete clearance.")

        # SUB-TAB 5: Re-Evaluation & Grievance Request
        with s_tab5:
            st.subheader("📝 Examination Re-Evaluation & Scrutiny Request")
            st.caption("Submit formal requests for re-checking of internal or external marks.")
            with st.form("reval_form"):
                sel_c = st.selectbox(
                    "Select Course",
                    [f"{e['course_code']} - {e['course_title']}" for e in data["enrollments"]],
                )
                comp = st.radio("Component for Scrutiny", ["External End-Term Marks", "Internal Sessional Marks", "Both"])
                reason = st.text_area("Justification / Discrepancy Description", placeholder="Explain reason for re-evaluation request...")
                if st.form_submit_button("Submit Re-Evaluation Application"):
                    st.success(f"Application for '{sel_c}' ({comp}) submitted successfully. Assigned Token: `JH-REV-2026-081`.")

        # SUB-TAB 6: AI Student Concierge
        with s_tab6:
            st.subheader("💬 AI Student Concierge")
            st.caption("Ask questions about your marks, syllabus, attendance recovery, or exam rules.")
            s_prompt = st.chat_input("Type your question for the academic assistant...")
            if s_prompt:
                ai_r = requests.post(f"{API_URL}/ai/chat", headers=headers, json={"message": s_prompt})
                if ai_r.status_code == 200:
                    st.markdown(ai_r.json()["reply"])


# =====================================================================
# SCREEN 3: FACULTY DASHBOARD
# =====================================================================
elif st.session_state.auth["role"] == "faculty":
    headers = {"Authorization": f"Bearer {st.session_state.auth['access_token']}"}

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
        [
            "📊 Analytics & Scorecards",
            "👥 Manage Students",
            "📚 Manage Courses",
            "📝 Enrollments & Batch Attendance",
            "📢 AI Notice Broadcast Hub",
            "💬 AI Academic Assistant",
        ]
    )

    # Fetch foundational data
    students_list = requests.get(f"{API_URL}/students", headers=headers).json()
    courses_list = requests.get(f"{API_URL}/courses", headers=headers).json()

    # --- TAB 1: ANALYTICS & STUDENT SCORECARDS ---
    with tab1:
        st.subheader("Departmental Academic Health & Analytics")
        an_res = requests.get(f"{API_URL}/analytics/department", headers=headers)

        if an_res.status_code == 200:
            an_data = an_res.json()
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Total Students Enrolled", an_data["total_students"])
            k2.metric("Active Department Courses", an_data["total_courses"])
            k3.metric("Batch Average SGPA", f"{an_data['average_sgpa']:.2f} / 10.0")
            k4.metric("Dept Attendance Average", f"{an_data['average_attendance_percentage']}%")

            st.divider()

            # Visual Charts
            ch1, ch2 = st.columns(2)
            with ch1:
                st.markdown("#### 📈 Subject-Wise Average Marks Breakdown")
                perf_df = pd.DataFrame(an_data["course_performance"])
                if not perf_df.empty:
                    chart_data = perf_df.set_index("code")[["average_internal", "average_external", "average_total"]]
                    chart_data.columns = ["Internal (Max 40)", "External (Max 60)", "Total (Max 100)"]
                    st.bar_chart(chart_data)
            with ch2:
                st.markdown("#### 🎯 Subject-Wise Average Attendance %")
                if not perf_df.empty:
                    att_chart = perf_df.set_index("code")[["average_attendance"]]
                    att_chart.columns = ["Attendance %"]
                    st.bar_chart(att_chart)

            # Attendance Shortage Watchlist
            st.divider()
            st.markdown("#### 🚨 Attendance Shortage & Debarment Watchlist (Ordinance 15)")
            if an_data["shortage_students"]:
                short_df_rows = []
                for s in an_data["shortage_students"]:
                    sub_str = ", ".join([f"{c['code']} ({c['pct']}%)" for c in s["shortage_courses"]])
                    short_df_rows.append({
                        "Student Name": s["name"],
                        "Enrollment No": s["enrollment_no"],
                        "Overall Attendance": f"{s['overall_attendance']}%",
                        "Shortage Subjects": sub_str,
                        "Status": "🔴 DEBARRED / WITHHELD",
                    })
                st.dataframe(pd.DataFrame(short_df_rows), use_container_width=True)
            else:
                st.success("No students currently below the 75% attendance threshold.")

        st.divider()
        st.subheader("Filter Enrollment Records & Individual Scorecard")
        col_f1, col_f2 = st.columns(2)
        selected_course = col_f1.selectbox(
            "Filter Enrollments by Course",
            ["All"] + [c["code"] for c in courses_list],
        )
        selected_student = col_f2.selectbox(
            "Inspect Individual Student Scorecard",
            [f"{s['id']} - {s['name']} ({s['enrollment_no']})" for s in students_list],
        )

        params = {}
        if selected_course != "All":
            params["course_code"] = selected_course

        enr_data = requests.get(f"{API_URL}/enrollments", headers=headers, params=params).json()
        if enr_data:
            st.dataframe(pd.DataFrame(enr_data), use_container_width=True)
        else:
            st.info("No matching enrollment records found.")

        if selected_student:
            st_id = int(selected_student.split(" - ")[0])
            sc_res = requests.get(f"{API_URL}/students/{st_id}", headers=headers).json()
            st.markdown(
                f"**Scorecard Summary for {sc_res['student']['name']}** — "
                f"**SGPA:** `{sc_res['sgpa']}` | "
                f"**Overall Attendance:** `{sc_res['overall_attendance_percentage']}%` "
                f"(`{sc_res['overall_attendance_eligibility']}`)"
            )

    # --- TAB 2: STUDENT CRUD + 1-CLICK AUTO-FILL ---
    with tab2:
        left, right = st.columns(2)
        with left:
            st.subheader("Add New Student")

            # 1-Click Form Auto-Fill Button
            if st.button("✨ 1-Click Auto-Fill Demo Student (Zaid Ahmed)"):
                st.session_state["demo_st_enr"] = "ENR-2023-104"
                st.session_state["demo_st_name"] = "Zaid Ahmed"
                st.session_state["demo_st_email"] = "zaid.ahmed@example.edu"
                st.session_state["demo_st_sem"] = 7
                st.session_state["demo_st_user"] = "zaid"

            with st.form("add_student_form", clear_on_submit=True):
                enr_no = st.text_input(
                    "Enrollment No",
                    value=st.session_state.get("demo_st_enr", "ENR-2023-105"),
                )
                name = st.text_input(
                    "Full Name",
                    value=st.session_state.get("demo_st_name", "Tariq Mansoor"),
                )
                email = st.text_input(
                    "Email",
                    value=st.session_state.get("demo_st_email", "tariq@example.edu"),
                )
                sem = st.number_input(
                    "Semester",
                    min_value=1,
                    max_value=8,
                    value=st.session_state.get("demo_st_sem", 7),
                )
                uname = st.text_input(
                    "Student Login Username",
                    value=st.session_state.get("demo_st_user", "tariq"),
                )
                pw = st.text_input("Student Login Password", value="student123")

                if st.form_submit_button("Create Student Record"):
                    r = requests.post(
                        f"{API_URL}/students",
                        headers=headers,
                        json={
                            "enrollment_no": enr_no,
                            "name": name,
                            "email": email,
                            "semester": sem,
                            "login_username": uname or None,
                            "login_password": pw,
                        },
                    )
                    if r.status_code == 201:
                        st.success(f"✅ Created student: {r.json()['name']}")
                        st.rerun()
                    else:
                        st.error(r.json().get("detail", "Error creating student"))

        with right:
            st.subheader("Existing Registered Students")
            st.dataframe(pd.DataFrame(students_list), use_container_width=True)
            del_st_id = st.number_input("Student ID to Delete", min_value=1, step=1)
            if st.button("Delete Student", type="secondary"):
                r = requests.delete(f"{API_URL}/students/{int(del_st_id)}", headers=headers)
                if r.status_code == 200:
                    st.success(r.json()["message"])
                    st.rerun()
                else:
                    st.error(r.json().get("detail", "Delete failed"))

    # --- TAB 3: COURSE CRUD + 1-CLICK AUTO-FILL ---
    with tab3:
        left_c, right_c = st.columns(2)
        with left_c:
            st.subheader("Add New Course")

            # 1-Click Auto-Fill Demo Course Button
            if st.button("✨ 1-Click Auto-Fill Demo Course (BTCSE-705 Cloud Computing)"):
                st.session_state["demo_c_code"] = "BTCSE-705"
                st.session_state["demo_c_title"] = "Cloud Computing & Virtualization"
                st.session_state["demo_c_credits"] = 4

            with st.form("add_course_form", clear_on_submit=True):
                c_code = st.text_input(
                    "Course Code",
                    value=st.session_state.get("demo_c_code", "BTCSE-706"),
                )
                c_title = st.text_input(
                    "Course Title",
                    value=st.session_state.get("demo_c_title", "Deep Learning & Neural Networks"),
                )
                c_credits = st.number_input(
                    "Credits",
                    min_value=1,
                    max_value=6,
                    value=st.session_state.get("demo_c_credits", 4),
                )
                c_int = st.number_input("Max Internal Marks", value=40.0)
                c_ext = st.number_input("Max External Marks", value=60.0)
                if st.form_submit_button("Create Course Record"):
                    r = requests.post(
                        f"{API_URL}/courses",
                        headers=headers,
                        json={
                            "code": c_code,
                            "title": c_title,
                            "credits": c_credits,
                            "max_internal": c_int,
                            "max_external": c_ext,
                        },
                    )
                    if r.status_code == 201:
                        st.success(f"✅ Added course: {r.json()['code']}")
                        st.rerun()
                    else:
                        st.error(r.json().get("detail", "Failed to add course"))

        with right_c:
            st.subheader("Department Course Catalog")
            st.dataframe(pd.DataFrame(courses_list), use_container_width=True)

    # --- TAB 4: ENROLLMENTS & 1-CLICK BATCH ATTENDANCE REGISTER ---
    with tab4:
        st.subheader("⏱️ 1-Click Daily Class Attendance Register (Fast Roll-Call)")
        st.caption("Faculty can complete daily roll-call for an entire batch in 5 seconds. All students default to Present.")

        batch_course = st.selectbox(
            "Select Course for Daily Roll-Call",
            [c["code"] for c in courses_list],
            key="batch_course_select",
        )
        enrs_for_batch = requests.get(
            f"{API_URL}/enrollments", headers=headers, params={"course_code": batch_course}
        ).json()

        if enrs_for_batch:
            st.write(f"Enrolled Students in **{batch_course}**: {len(enrs_for_batch)}")
            records_to_submit = []

            cols = st.columns(min(len(enrs_for_batch), 3))
            for i, enr in enumerate(enrs_for_batch):
                with cols[i % len(cols)]:
                    is_pres = st.checkbox(
                        f"{enr['student_name']} ({enr['enrollment_no']})",
                        value=True,
                        key=f"batch_att_{enr['student_id']}_{batch_course}",
                    )
                    st.caption(
                        f"Current: {enr['classes_attended']}/{enr['classes_held']} "
                        f"({enr['attendance_percentage']}%)"
                    )
                    records_to_submit.append({
                        "student_id": enr["student_id"],
                        "is_present": is_pres,
                    })

            if st.button("🚀 Submit Daily Class Attendance (+1 Held)", use_container_width=True):
                resp = requests.post(
                    f"{API_URL}/attendance/batch-register",
                    headers=headers,
                    json={"course_code": batch_course, "records": records_to_submit},
                )
                if resp.status_code == 200:
                    res_data = resp.json()
                    st.success(
                        f"✅ Attendance Recorded! Updated {res_data['total_records_updated']} student(s) "
                        f"({res_data['present_count']} Present, {res_data['absent_count']} Absent)."
                    )
                    st.rerun()
                else:
                    st.error("Failed to submit batch attendance.")
        else:
            st.info(f"No students currently enrolled in course {batch_course}.")

        st.divider()

        # Individual Enrollment & Marks Management
        col_e1, col_e2 = st.columns(2)
        with col_e1:
            st.subheader("Enroll Student in Course")
            if st.button("✨ 1-Click Auto-Fill Demo Marks"):
                st.session_state["demo_m_int"] = 34.0
                st.session_state["demo_m_ext"] = 48.0
                st.session_state["demo_m_held"] = 40
                st.session_state["demo_m_att"] = 36

            with st.form("enroll_form", clear_on_submit=True):
                st_choice = st.selectbox(
                    "Student",
                    [f"{s['id']} - {s['name']}" for s in students_list],
                )
                c_choice = st.selectbox("Course", [c["code"] for c in courses_list])
                int_m = st.number_input(
                    "Internal Marks (Max 40)",
                    min_value=0.0,
                    value=st.session_state.get("demo_m_int", 30.0),
                )
                ext_m = st.number_input(
                    "External Marks (Max 60)",
                    min_value=0.0,
                    value=st.session_state.get("demo_m_ext", 45.0),
                )
                c_held = st.number_input(
                    "Classes Held",
                    min_value=0,
                    value=st.session_state.get("demo_m_held", 40),
                )
                c_att = st.number_input(
                    "Classes Attended",
                    min_value=0,
                    value=st.session_state.get("demo_m_att", 32),
                )

                if st.form_submit_button("Save Enrollment & Marks"):
                    r = requests.post(
                        f"{API_URL}/enrollments",
                        headers=headers,
                        json={
                            "student_id": int(st_choice.split(" - ")[0]),
                            "course_code": c_choice,
                            "internal_marks": int_m,
                            "external_marks": ext_m,
                            "classes_held": c_held,
                            "classes_attended": c_att,
                        },
                    )
                    if r.status_code == 201:
                        st.success("✅ Enrollment and marks saved successfully.")
                        st.rerun()
                    else:
                        st.error(r.json().get("detail", "Validation error"))

        with col_e2:
            st.subheader("Update Existing Record")
            with st.form("update_enroll_form"):
                enr_id = st.number_input("Enrollment ID", min_value=1, step=1)
                u_int = st.number_input("New Internal Marks", min_value=0.0, value=35.0)
                u_ext = st.number_input("New External Marks", min_value=0.0, value=50.0)
                u_held = st.number_input("New Classes Held", min_value=0, value=40)
                u_att = st.number_input("New Classes Attended", min_value=0, value=36)

                if st.form_submit_button("Update Enrollment Record"):
                    r = requests.put(
                        f"{API_URL}/enrollments/{int(enr_id)}",
                        headers=headers,
                        json={
                            "internal_marks": u_int,
                            "external_marks": u_ext,
                            "classes_held": u_held,
                            "classes_attended": u_att,
                        },
                    )
                    if r.status_code == 200:
                        st.success(f"✅ Updated Enrollment ID {int(enr_id)}")
                        st.rerun()
                    else:
                        st.error(r.json().get("detail", "Update failed"))

    # --- TAB 5: AI NOTICE & DEADLINE BROADCAST HUB ---
    with tab5:
        st.subheader("📢 AI Notice & Deadline Broadcast Hub")
        st.caption("Replaces dry website PDFs with targeted, proactive university alerts.")

        col_t1, col_t2 = st.columns([1, 2])
        with col_t1:
            st.markdown("**1. Select Notice Template**")
            notice_choice = st.radio(
                "Circular Category",
                [
                    "📝 Exam Form & Late Fee Alert",
                    "📄 Marksheet Collection Window",
                    "🚨 75% Attendance Shortage Warning",
                    "✍️ Custom AI Draft",
                ],
            )
            target_audience = st.selectbox(
                "Target Audience",
                [
                    "All 7th Semester B.Tech CSE",
                    "Attendance Shortage Students Only (<75%)",
                    "Dean's Honors List (SGPA >= 8.5)",
                ],
            )
            channel = st.radio("Dispatch Channel", ["📱 WhatsApp AI Bot", "💬 SMS Gateway", "📧 Institutional Email"])

        with col_t2:
            st.markdown("**2. AI Live Preview & Notice Content**")
            if notice_choice == "📝 Exam Form & Late Fee Alert":
                default_notice = (
                    "JAMIA HAMDARD — SEST DEPT OF CSE\n"
                    "Ref: JH/SEST/CSE/2026/NOT-884\n\n"
                    "URGENT: B.Tech CSE 7th Semester Exam Form Submission is closing on 30-Nov-2026 (5:00 PM).\n"
                    "Submission after deadline carries a ₹1,000 late fine.\n"
                    "Portal: https://jamiahamdard.edu/examinations/portal\n"
                    "Prerequisite: Minimum 75% attendance in theory & labs."
                )
            elif notice_choice == "📄 Marksheet Collection Window":
                default_notice = (
                    "JAMIA HAMDARD — SEST DEPT OF CSE\n"
                    "Ref: JH/SEST/CSE/2026/MRK-102\n\n"
                    "Official 7th Semester physical grade sheets are ready for collection at Room 204, SEST 2nd Floor.\n"
                    "Timings: Mon–Fri, 10:00 AM – 3:00 PM.\n"
                    "Bring: Original Student ID Card & No-Dues Clearance Slip."
                )
            elif notice_choice == "🚨 75% Attendance Shortage Warning":
                an_res = requests.get(f"{API_URL}/analytics/department", headers=headers)
                short_names = "Diya Patel"
                if an_res.status_code == 200:
                    short_names = ", ".join([s["name"] for s in an_res.json()["shortage_students"]]) or "None"
                default_notice = (
                    f"JAMIA HAMDARD — SEST DEPT OF CSE\n"
                    f"FINAL ATTENDANCE DEBARMENT NOTICE (Ordinance 15)\n\n"
                    f"The following student(s) have attendance below 75% and face exam debarment: {short_names}.\n"
                    f"Report to the Course Coordinator (Ms. Gautami Tripathi) / HOD CSE immediately with undertakings."
                )
            else:
                default_notice = "Draft custom departmental notice here..."

            edited_notice = st.text_area("Editable Circular Text", value=default_notice, height=180)

            if st.button("📤 Dispatch Academic Broadcast", use_container_width=True):
                st.success("✅ Broadcast dispatched successfully to target recipients!")
                st.balloons()
                receipts = [
                    {"Recipient": "Aarav Sharma", "Target": "+91 98765 43210", "Channel": channel, "Status": "DELIVERED (0.4s)", "Receipt": "ACK-701-A"},
                    {"Recipient": "Diya Patel", "Target": "+91 98111 22334", "Channel": channel, "Status": "DELIVERED (0.6s)", "Receipt": "ACK-701-B"},
                    {"Recipient": "Rohan Verma", "Target": "+91 98222 33445", "Channel": channel, "Status": "DELIVERED (0.5s)", "Receipt": "ACK-701-C"},
                ]
                st.dataframe(pd.DataFrame(receipts), use_container_width=True)

    # --- TAB 6: AI ACADEMIC ASSISTANT (TOOL CALLING #1 + #5) ---
    with tab6:
        st.subheader("💬 AI Academic Assistant (Tool Calling #1 + #5)")
        st.caption("Direct natural language access to departmental database and academic rules.")

        st.write("💡 **Quick Queries (Click to Run):**")
        p1, p2, p3, p4 = st.columns(4)
        query_to_send = None
        if p1.button("🚨 Debarred Students List"):
            query_to_send = "Who is debarred due to attendance shortage?"
        if p2.button("🧮 Diya Attendance Recovery"):
            query_to_send = "Calculate attendance recovery for Diya Patel"
        if p3.button("📝 Draft Exam Form Circular"):
            query_to_send = "Draft exam form submission deadline notice"
        if p4.button("📊 Department Performance"):
            query_to_send = "Show department average SGPA and attendance"

        if "chat_messages" not in st.session_state:
            st.session_state.chat_messages = [
                {
                    "role": "assistant",
                    "content": "👋 Assalamu Alaikum! I am the **Jamia Hamdard CSE Academic Assistant**.\n\n"
                    "Ask me about student eligibility, attendance recovery calculations, exam form notices, or department performance analytics.",
                }
            ]

        user_prompt = st.chat_input("Ask a question about students, attendance, or circulars...")
        prompt = query_to_send or user_prompt

        if prompt:
            st.session_state.chat_messages.append({"role": "user", "content": prompt})
            try:
                ai_res = requests.post(f"{API_URL}/ai/chat", headers=headers, json={"message": prompt})
                if ai_res.status_code == 200:
                    data = ai_res.json()
                    reply_text = data["reply"]
                    if data.get("tool_called"):
                        reply_text += f"\n\n*(Executed Tool: `{data['tool_called']}`)*"
                    st.session_state.chat_messages.append({"role": "assistant", "content": reply_text})
                else:
                    st.session_state.chat_messages.append({"role": "assistant", "content": "Sorry, could not process request."})
            except Exception as e:
                st.session_state.chat_messages.append({"role": "assistant", "content": f"Connection error: {e}"})

        for msg in st.session_state.chat_messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
