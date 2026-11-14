import pandas as pd
import requests
import streamlit as st

API_URL = "http://127.0.0.1:8000"

st.set_page_config(
    page_title="Jamia Hamdard CSE — Academic Portal", layout="wide"
)
st.title("Departmental Academic Record, Result & Attendance System")
st.caption(
    "B.Tech CSE 7th Semester (Project-II: BTCSE 701) — Localhost Prototype"
)

if "auth" not in st.session_state:
    st.session_state.auth = None

# Sidebar Demo Credentials & Logout
with st.sidebar:
    st.subheader("System Access")
    if st.session_state.auth:
        st.success(
            f"Logged in: **{st.session_state.auth['username']}** ({st.session_state.auth['role'].upper()})"
        )
        if st.button("Logout", use_container_width=True):
            st.session_state.auth = None
            st.rerun()
    else:
        st.info(
            "**Demo Accounts (Seeded):**\n"
            "- **Faculty:** `faculty` / `faculty123`\n"
            "- **Student 1:** `aarav` / `student123`\n"
            "- **Student 2:** `diya` / `student123`\n"
            "- **Student 3:** `rohan` / `student123`"
        )

# =====================================================================
# SCREEN 1: LOGIN VIEW
# =====================================================================
if not st.session_state.auth:
    st.subheader("Login to Portal")
    with st.form("login_form"):
        username = st.text_input("Username")
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
                    st.error(res.json().get("detail", "Login failed"))
            except requests.exceptions.ConnectionError:
                st.error(
                    "Cannot reach FastAPI backend. Run `uvicorn main:app --reload` first."
                )

# =====================================================================
# SCREEN 2: STUDENT DASHBOARD (READ-ONLY PERSONAL SCORECARD)
# =====================================================================
elif st.session_state.auth["role"] == "student":
    headers = {"Authorization": f"Bearer {st.session_state.auth['access_token']}"}
    res = requests.get(f"{API_URL}/me/scorecard", headers=headers)

    if res.status_code != 200:
        st.error(res.json().get("detail", "Could not load scorecard"))
    else:
        data = res.json()
        st_info = data["student"]

        st.subheader(
            f"Student Scorecard: {st_info['name']} ({st_info['enrollment_no']})"
        )
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Semester", st_info["semester"])
        c2.metric("Calculated SGPA", f"{data['sgpa']:.2f}")
        c3.metric(
            "Overall Attendance",
            f"{data['overall_attendance_percentage']}%"
            if data["overall_attendance_percentage"] is not None
            else "Unavailable",
        )
        c4.metric(
            "Attendance Status", data["overall_attendance_eligibility"]
        )

        st.divider()
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
        else:
            st.info("No course enrollments found for this semester.")
        st.caption(data["grading_note"])

# =====================================================================
# SCREEN 3: FACULTY DASHBOARD
# =====================================================================
elif st.session_state.auth["role"] == "faculty":
    headers = {"Authorization": f"Bearer {st.session_state.auth['access_token']}"}
    tab1, tab2, tab3, tab4 = st.tabs(
        [
            "Academic Records & Scorecards",
            "Manage Students",
            "Manage Courses",
            "Enrollments, Marks & Attendance",
        ]
    )

    # --- TAB 1: VIEW RECORDS & STUDENT SCORECARDS ---
    with tab1:
        st.subheader("Search & Filter Enrollment Records")
        students_list = requests.get(
            f"{API_URL}/students", headers=headers
        ).json()
        courses_list = requests.get(
            f"{API_URL}/courses", headers=headers
        ).json()

        col_f1, col_f2 = st.columns(2)
        selected_course = col_f1.selectbox(
            "Filter by Course",
            ["All"] + [c["code"] for c in courses_list],
        )
        selected_student = col_f2.selectbox(
            "Inspect Individual Student Scorecard",
            [f"{s['id']} - {s['name']} ({s['enrollment_no']})" for s in students_list],
        )

        params = {}
        if selected_course != "All":
            params["course_code"] = selected_course

        enr_data = requests.get(
            f"{API_URL}/enrollments", headers=headers, params=params
        ).json()
        if enr_data:
            st.dataframe(pd.DataFrame(enr_data), use_container_width=True)
        else:
            st.info("No matching enrollment records.")

        if selected_student:
            st.divider()
            st_id = int(selected_student.split(" - ")[0])
            sc_res = requests.get(
                f"{API_URL}/students/{st_id}", headers=headers
            ).json()
            st.markdown(
                f"**Scorecard Summary for {sc_res['student']['name']}** — "
                f"**SGPA:** `{sc_res['sgpa']}` | "
                f"**Overall Attendance:** `{sc_res['overall_attendance_percentage']}%` "
                f"(`{sc_res['overall_attendance_eligibility']}`)"
            )

    # --- TAB 2: STUDENT CRUD ---
    with tab2:
        left, right = st.columns(2)
        with left:
            st.subheader("Add New Student")
            with st.form("add_student_form", clear_on_submit=True):
                enr_no = st.text_input("Enrollment No (e.g., ENR-2023-105)")
                name = st.text_input("Full Name")
                email = st.text_input("Email")
                sem = st.number_input("Semester", min_value=1, max_value=8, value=7)
                uname = st.text_input("Student Login Username")
                pw = st.text_input("Student Login Password", value="student123")
                if st.form_submit_button("Create Student"):
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
                        st.success(f"Created student: {r.json()['name']}")
                        st.rerun()
                    else:
                        st.error(r.json().get("detail", "Error creating student"))

        with right:
            st.subheader("Existing Students")
            st.dataframe(pd.DataFrame(students_list), use_container_width=True)
            del_st_id = st.number_input("Student ID to Delete", min_value=1, step=1)
            if st.button("Delete Student"):
                r = requests.delete(f"{API_URL}/students/{int(del_st_id)}", headers=headers)
                if r.status_code == 200:
                    st.success(r.json()["message"])
                    st.rerun()
                else:
                    st.error(r.json().get("detail", "Delete failed"))

    # --- TAB 3: COURSE CRUD ---
    with tab3:
        left_c, right_c = st.columns(2)
        with left_c:
            st.subheader("Add New Course")
            with st.form("add_course_form", clear_on_submit=True):
                c_code = st.text_input("Course Code (e.g., BHM-701)")
                c_title = st.text_input("Course Title")
                c_credits = st.number_input("Credits", min_value=1, max_value=6, value=3)
                c_int = st.number_input("Max Internal Marks", value=40.0)
                c_ext = st.number_input("Max External Marks", value=60.0)
                if st.form_submit_button("Create Course"):
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
                        st.success(f"Added course: {r.json()['code']}")
                        st.rerun()
                    else:
                        st.error(r.json().get("detail", "Failed to add course"))

        with right_c:
            st.subheader("Configured Courses")
            st.dataframe(pd.DataFrame(courses_list), use_container_width=True)

    # --- TAB 4: ENROLLMENTS, MARKS & ATTENDANCE ---
    with tab4:
        col_e1, col_e2 = st.columns(2)
        with col_e1:
            st.subheader("Enroll Student & Record Marks")
            with st.form("enroll_form", clear_on_submit=True):
                st_choice = st.selectbox(
                    "Student",
                    [f"{s['id']} - {s['name']}" for s in students_list],
                )
                c_choice = st.selectbox(
                    "Course", [c["code"] for c in courses_list]
                )
                int_m = st.number_input("Internal Marks", min_value=0.0, value=30.0)
                ext_m = st.number_input("External Marks", min_value=0.0, value=45.0)
                c_held = st.number_input("Classes Held", min_value=0, value=40)
                c_att = st.number_input("Classes Attended", min_value=0, value=32)

                if st.form_submit_button("Save Enrollment"):
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
                        st.success("Enrollment saved.")
                        st.rerun()
                    else:
                        st.error(r.json().get("detail", "Validation error"))

        with col_e2:
            st.subheader("Update Existing Marks / Attendance")
            with st.form("update_enroll_form"):
                enr_id = st.number_input("Enrollment ID", min_value=1, step=1)
                u_int = st.number_input("New Internal Marks", min_value=0.0, value=35.0)
                u_ext = st.number_input("New External Marks", min_value=0.0, value=50.0)
                u_held = st.number_input("New Classes Held", min_value=0, value=40)
                u_att = st.number_input("New Classes Attended", min_value=0, value=36)

                if st.form_submit_button("Update Record"):
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
                        st.success(f"Updated Enrollment ID {int(enr_id)}")
                        st.rerun()
                    else:
                        st.error(r.json().get("detail", "Update failed"))
