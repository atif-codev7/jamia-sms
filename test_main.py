import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from main import Base, app, get_db, seed_fictional_data

TEST_DB_FILE = "./test_academic_records.db"
TEST_DATABASE_URL = f"sqlite:///{TEST_DB_FILE}"

test_engine = create_engine(
    TEST_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=test_engine
)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_clean_test_db():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    with TestingSessionLocal() as db:
        seed_fictional_data(db)
    yield
    Base.metadata.drop_all(bind=test_engine)
    if os.path.exists(TEST_DB_FILE):
        try:
            os.remove(TEST_DB_FILE)
        except OSError:
            pass


client = TestClient(app)


def get_auth_headers(username: str, password: str) -> dict:
    res = client.post(
        "/auth/login", json={"username": username, "password": password}
    )
    assert res.status_code == 200
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# TC-01: Successful login with valid credentials
def test_01_valid_login():
    res = client.post(
        "/auth/login", json={"username": "faculty", "password": "faculty123"}
    )
    assert res.status_code == 200
    assert res.json()["role"] == "faculty"
    assert "access_token" in res.json()


# TC-02: Failed login with invalid credentials
def test_02_invalid_login():
    res = client.post(
        "/auth/login", json={"username": "faculty", "password": "wrongpassword"}
    )
    assert res.status_code == 401


# TC-03: Student blocked from faculty-only endpoints
def test_03_student_blocked_from_faculty_routes():
    headers = get_auth_headers("aarav", "student123")
    res = client.post(
        "/courses",
        headers=headers,
        json={
            "code": "BTCSE-999",
            "title": "Unauthorized Course",
            "credits": 3,
            "max_internal": 40,
            "max_external": 60,
        },
    )
    assert res.status_code == 403


# TC-04: Student cannot access another student's scorecard
def test_04_student_isolated_scorecard():
    headers = get_auth_headers("aarav", "student123")
    # Student trying to hit faculty student lookup for Diya (ID 2) gets 403
    res_other = client.get("/students/2", headers=headers)
    assert res_other.status_code == 403

    # /me/scorecard strictly returns Aarav's own record from JWT token
    res_me = client.get("/me/scorecard", headers=headers)
    assert res_me.status_code == 200
    assert res_me.json()["student"]["name"] == "Aarav Sharma"


# TC-05: Successful student creation by faculty
def test_05_create_student_success():
    headers = get_auth_headers("faculty", "faculty123")
    res = client.post(
        "/students",
        headers=headers,
        json={
            "enrollment_no": "ENR-2023-104",
            "name": "kabir khan",
            "email": "kabir@example.edu",
            "semester": 7,
        },
    )
    assert res.status_code == 201
    assert res.json()["name"] == "Kabir Khan"  # Title-cased automatically


# TC-06: Duplicate student enrollment number rejected
def test_06_duplicate_student_rejected():
    headers = get_auth_headers("faculty", "faculty123")
    res = client.post(
        "/students",
        headers=headers,
        json={
            "enrollment_no": "ENR-2023-101",
            "name": "Duplicate User",
            "email": "unique_dup@example.edu",
            "semester": 7,
        },
    )
    assert res.status_code == 400


# TC-07: Marks above configured course maximum rejected (40 internal / 60 external)
def test_07_marks_above_maximum_rejected():
    headers = get_auth_headers("faculty", "faculty123")
    res = client.post(
        "/enrollments",
        headers=headers,
        json={
            "student_id": 2,
            "course_code": "BTCSE-DED51",
            "internal_marks": 45.0,  # Exceeds max_internal=40
            "external_marks": 50.0,
            "classes_held": 20,
            "classes_attended": 18,
        },
    )
    assert res.status_code == 400
    assert "Internal marks" in res.json()["detail"]


# TC-08: Negative marks rejected by Pydantic validation
def test_08_negative_marks_rejected():
    headers = get_auth_headers("faculty", "faculty123")
    res = client.post(
        "/enrollments",
        headers=headers,
        json={
            "student_id": 2,
            "course_code": "BTCSE-DED51",
            "internal_marks": -5.0,
            "external_marks": 40.0,
            "classes_held": 20,
            "classes_attended": 15,
        },
    )
    assert res.status_code == 422


# TC-09: Duplicate student-course enrollment rejected
def test_09_duplicate_enrollment_rejected():
    headers = get_auth_headers("faculty", "faculty123")
    res = client.post(
        "/enrollments",
        headers=headers,
        json={
            "student_id": 1,
            "course_code": "BTCSE-702",  # Aarav is already enrolled in BTCSE-702
            "internal_marks": 30.0,
            "external_marks": 50.0,
            "classes_held": 30,
            "classes_attended": 25,
        },
    )
    assert res.status_code == 400


# TC-10: Attendance percentage calculated accurately
def test_10_attendance_percentage_calculation():
    headers = get_auth_headers("aarav", "student123")
    scorecard = client.get("/me/scorecard", headers=headers).json()
    java_enr = next(
        e for e in scorecard["enrollments"] if e["course_code"] == "BTCSE-702"
    )
    # 36 / 40 * 100 = 90.0%
    assert java_enr["attendance_percentage"] == 90.0
    assert java_enr["attendance_eligibility"] == "Eligible"


# TC-11: Attendance eligibility (<75% Shortage) is separate from academic grade
def test_11_attendance_shortage_does_not_force_f_grade():
    headers = get_auth_headers("diya", "student123")
    scorecard = client.get("/me/scorecard", headers=headers).json()
    adbms_enr = next(
        e for e in scorecard["enrollments"] if e["course_code"] == "BTCSE-704"
    )
    # 24 / 40 = 60.0% (<75% -> Shortage), but marks 32+42=74 -> Grade 'A' preserved
    assert adbms_enr["attendance_percentage"] == 60.0
    assert adbms_enr["attendance_eligibility"] == "Shortage"
    assert adbms_enr["grade"] == "A"


# TC-12: Classes attended cannot exceed classes held
def test_12_classes_attended_exceeding_held_rejected():
    headers = get_auth_headers("faculty", "faculty123")
    res = client.post(
        "/enrollments",
        headers=headers,
        json={
            "student_id": 2,
            "course_code": "BTCSE-703",
            "internal_marks": 30.0,
            "external_marks": 40.0,
            "classes_held": 20,
            "classes_attended": 25,
        },
    )
    assert res.status_code == 400


# TC-13: Zero classes held does not cause division by zero
def test_13_zero_classes_held_safe():
    headers = get_auth_headers("rohan", "student123")
    scorecard = client.get("/me/scorecard", headers=headers).json()
    dec_enr = scorecard["enrollments"][0]
    assert dec_enr["classes_held"] == 0
    assert dec_enr["attendance_percentage"] is None
    assert dec_enr["attendance_eligibility"] == "Unavailable"


# TC-14: Credit-weighted SGPA verified manually against expected math
def test_14_sgpa_manual_verification():
    headers = get_auth_headers("aarav", "student123")
    scorecard = client.get("/me/scorecard", headers=headers).json()
    # Aarav's seeded marks:
    # BTCSE-702 (4 cr): 36+54 = 90% -> O (10 GP) -> 4 * 10 = 40
    # BTCSE-704 (4 cr): 34+48 = 82% -> A+ (9 GP) -> 4 * 9  = 36
    # BTCSE-DED51 (3 cr): 32+45 = 77% -> A (8 GP) -> 3 * 8 = 24
    # Total = 100 / 11 credits = 9.09
    assert scorecard["total_credits_enrolled"] == 11
    assert scorecard["sgpa"] == 9.09


# TC-15: Missing records return 404 Not Found
def test_15_missing_record_returns_404():
    headers = get_auth_headers("faculty", "faculty123")
    res = client.get("/students/9999", headers=headers)
    assert res.status_code == 404


# TC-16: Department analytics calculates batch KPIs and course performance
def test_16_department_analytics():
    headers = get_auth_headers("faculty", "faculty123")
    res = client.get("/analytics/department", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total_students"] == 3
    assert data["total_courses"] >= 4
    assert data["average_sgpa"] > 0
    assert data["eligible_count"] >= 1
    assert data["shortage_count"] >= 1
    assert len(data["course_performance"]) >= 4


# TC-17: Attendance recovery calculator computes exact consecutive classes needed for shortage
def test_17_attendance_recovery_shortage():
    headers = get_auth_headers("diya", "student123")
    res = client.get("/me/recovery-calculator", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["student_name"] == "Diya Patel"
    assert data["overall_attendance_eligibility"] == "Shortage"
    assert data["overall_consecutive_needed"] > 0
    assert data["overall_buffer_can_miss"] == 0
    # In BTCSE-704, Diya attended 24 of 40 (60%). Needed = ceil(3*40 - 4*24) = 24
    adbms = next(c for c in data["courses"] if c["course_code"] == "BTCSE-704")
    assert adbms["consecutive_classes_needed"] == 24
    assert adbms["status"] == "Shortage"


# TC-18: Attendance recovery calculator provides buffer classes for eligible student
def test_18_attendance_recovery_eligible_buffer():
    headers = get_auth_headers("aarav", "student123")
    res = client.get("/me/recovery-calculator", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["overall_attendance_eligibility"] == "Eligible"
    assert data["overall_consecutive_needed"] == 0
    assert data["overall_buffer_can_miss"] >= 0


# TC-19: Digital Admit Card gate unlocks for eligible student (Aarav)
def test_19_admit_card_eligible_unlocked():
    headers = get_auth_headers("aarav", "student123")
    res = client.get("/me/admit-card", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["is_eligible"] is True
    assert "ELIGIBLE" in data["status_text"]
    assert data["debarment_reason"] is None
    assert len(data["enrolled_courses"]) == 3
    assert data["qr_verification_hash"] is not None


# TC-20: Digital Admit Card gate locks and debars student with shortage (Diya)
def test_20_admit_card_shortage_debarred():
    headers = get_auth_headers("diya", "student123")
    res = client.get("/me/admit-card", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["is_eligible"] is False
    assert "DEBARRED" in data["status_text"]
    assert "Ordinance 15" in data["debarment_reason"]
    assert data["hall_ticket_no"] == "WITHHELD-SHORTAGE"


# TC-21: Digital No-Dues clearance status check
def test_21_digital_no_dues_clearance():
    headers = get_auth_headers("aarav", "student123")
    res = client.get("/me/no-dues", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["library"]["cleared"] is True
    assert data["accounts"]["cleared"] is True
    assert data["is_all_cleared"] is True


# TC-22: Batch attendance register increments classes correctly
def test_22_batch_attendance_register():
    headers = get_auth_headers("faculty", "faculty123")
    res = client.post(
        "/attendance/batch-register",
        headers=headers,
        json={
            "course_code": "BTCSE-702",
            "records": [
                {"student_id": 1, "is_present": True},
                {"student_id": 2, "is_present": False},
            ],
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["course_code"] == "BTCSE-702"
    assert data["total_records_updated"] == 2
    assert data["present_count"] == 1
    assert data["absent_count"] == 1


# TC-23: AI Chat assistant answers shortage queries via tool calling
def test_23_ai_chat_shortage_tool():
    res = client.post("/ai/chat", json={"message": "Who is debarred due to attendance shortage?"})
    assert res.status_code == 200
    data = res.json()
    assert data["tool_called"] == "query_attendance_shortages"
    assert "Diya Patel" in data["reply"]
    assert "Ordinance 15" in data["reply"]


# TC-24: AI Chat assistant drafts official exam form notice
def test_24_ai_chat_exam_notice_tool():
    res = client.post("/ai/chat", json={"message": "Draft exam form submission deadline notice"})
    assert res.status_code == 200
    data = res.json()
    assert data["tool_called"] == "draft_exam_form_notice"
    assert "JAMIA HAMDARD" in data["reply"].upper()
    assert "LATE" in data["reply"].upper()


# TC-25: WhatsApp Webhook returns valid TwiML XML for Twilio
def test_25_whatsapp_webhook_twiml():
    res = client.post(
        "/webhook/whatsapp",
        data={"Body": "Who is debarred due to attendance shortage?", "From": "whatsapp:+919876543210"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert res.status_code == 200
    assert "application/xml" in res.headers["content-type"]
    assert "<Response>" in res.text
    assert "<Message>" in res.text
    assert "Diya Patel" in res.text


# TC-26: WhatsApp Webhook returns JSON for web chat simulator
def test_26_whatsapp_webhook_json():
    res = client.post(
        "/webhook/whatsapp?format=json",
        json={"Body": "What is Aarav's SGPA?", "From": "whatsapp:+919876543210"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "delivered"
    assert "Aarav Sharma" in data["reply"]
    assert "<Response>" in data["twiml_xml"]


