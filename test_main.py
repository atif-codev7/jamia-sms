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
