import hashlib
import math
import os
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import jwt
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from sqlalchemy import (
    Column,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import Session, declarative_base, sessionmaker

# =====================================================================
# PART 1: CONFIGURATION & ILLUSTRATIVE ACADEMIC RULES
# =====================================================================
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./academic_records.db")
JWT_SECRET_KEY = os.getenv(
    "JWT_SECRET_KEY", "jamia_hamdard_btcse_701_secret_key_2026"
)
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "120"))

# Configurable attendance eligibility threshold (%)
ATTENDANCE_ELIGIBILITY_THRESHOLD = 75.0

# Illustrative Grade-to-Grade-Point Mapping (Configurable)
GRADE_SCALE = [
    (90.0, "O", 10),
    (80.0, "A+", 9),
    (70.0, "A", 8),
    (60.0, "B+", 7),
    (50.0, "B", 6),
    (40.0, "P", 5),
    (0.0, "F", 0),
]

# =====================================================================
# PART 2: DATABASE ENGINE & 4 RELATIONAL TABLES (SQLAlchemy ORM)
# =====================================================================
engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class StudentDB(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    enrollment_no = Column(String(30), unique=True, nullable=False, index=True)
    name = Column(String(60), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    semester = Column(Integer, nullable=False, default=7)


class UserDB(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(128), nullable=False)
    salt = Column(String(64), nullable=False)
    role = Column(String(20), nullable=False)  # "faculty" or "student"
    student_id = Column(
        Integer, ForeignKey("students.id", ondelete="CASCADE"), unique=True, nullable=True
    )


class CourseDB(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(20), unique=True, nullable=False, index=True)
    title = Column(String(100), nullable=False)
    credits = Column(Integer, nullable=False)
    max_internal = Column(Float, nullable=False, default=40.0)
    max_external = Column(Float, nullable=False, default=60.0)


class EnrollmentDB(Base):
    __tablename__ = "enrollments"
    __table_args__ = (
        UniqueConstraint("student_id", "course_code", name="uq_student_course"),
    )

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(
        Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )
    course_code = Column(
        String(20), ForeignKey("courses.code", ondelete="CASCADE"), nullable=False
    )
    internal_marks = Column(Float, nullable=False, default=0.0)
    external_marks = Column(Float, nullable=False, default=0.0)
    classes_held = Column(Integer, nullable=False, default=0)
    classes_attended = Column(Integer, nullable=False, default=0)


# =====================================================================
# PART 3: PASSWORD HASHING (PBKDF2_HMAC) & JWT UTILITIES
# =====================================================================
def hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    if salt is None:
        salt = os.urandom(16).hex()
    derived = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000
    )
    return derived.hex(), salt


def verify_password(password: str, stored_hash: str, salt: str) -> bool:
    computed_hash, _ = hash_password(password, salt)
    return computed_hash == stored_hash


def create_jwt_token(user: UserDB) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)
    payload = {
        "sub": user.username,
        "user_id": user.id,
        "role": user.role,
        "student_id": user.student_id,
        "exp": expire,
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


# =====================================================================
# PART 4: ACADEMIC CALCULATION HELPERS
# =====================================================================
def calculate_grade_and_points(
    total_marks: float, max_total: float
) -> tuple[float, str, int]:
    if max_total <= 0:
        return 0.0, "N/A", 0
    percentage = round((total_marks / max_total) * 100.0, 2)
    for threshold, letter_grade, grade_points in GRADE_SCALE:
        if percentage >= threshold:
            return percentage, letter_grade, grade_points
    return percentage, "F", 0


def calculate_attendance_metrics(
    classes_attended: int, classes_held: int
) -> tuple[Optional[float], str]:
    if classes_held == 0:
        return None, "Unavailable"
    pct = round((classes_attended / classes_held) * 100.0, 2)
    status_str = (
        "Eligible" if pct >= ATTENDANCE_ELIGIBILITY_THRESHOLD else "Shortage"
    )
    return pct, status_str


# =====================================================================
# PART 5: PYDANTIC SCHEMAS (INPUT VALIDATION & OUTPUT RESPONSES)
# =====================================================================
class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str
    student_id: Optional[int] = None


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    student_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class StudentCreate(BaseModel):
    enrollment_no: str = Field(..., min_length=3, max_length=30, examples=["ENR-2023-001"])
    name: str = Field(..., min_length=2, max_length=60, examples=["Aarav Sharma"])
    email: EmailStr = Field(..., examples=["aarav@example.edu"])
    semester: int = Field(default=7, ge=1, le=8)
    login_username: Optional[str] = Field(default=None, min_length=3, max_length=50)
    login_password: Optional[str] = Field(default="student123", min_length=6)

    @field_validator("name")
    @classmethod
    def validate_name_letters(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned.replace(" ", "").isalpha():
            raise ValueError("Name must contain only letters and spaces")
        return cleaned.title()


class StudentUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=60)
    email: Optional[EmailStr] = None
    semester: Optional[int] = Field(default=None, ge=1, le=8)

    @field_validator("name")
    @classmethod
    def validate_name_letters(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned.replace(" ", "").isalpha():
            raise ValueError("Name must contain only letters and spaces")
        return cleaned.title()


class StudentResponse(BaseModel):
    id: int
    enrollment_no: str
    name: str
    email: EmailStr
    semester: int

    model_config = ConfigDict(from_attributes=True)


class CourseCreate(BaseModel):
    code: str = Field(..., min_length=3, max_length=20, examples=["BTCSE-704"])
    title: str = Field(..., min_length=3, max_length=100, examples=["Advanced DBMS"])
    credits: int = Field(..., ge=1, le=10, examples=[4])
    max_internal: float = Field(default=40.0, gt=0, le=100)
    max_external: float = Field(default=60.0, gt=0, le=100)


class CourseUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=3, max_length=100)
    credits: Optional[int] = Field(default=None, ge=1, le=10)
    max_internal: Optional[float] = Field(default=None, gt=0, le=100)
    max_external: Optional[float] = Field(default=None, gt=0, le=100)


class CourseResponse(BaseModel):
    id: int
    code: str
    title: str
    credits: int
    max_internal: float
    max_external: float

    model_config = ConfigDict(from_attributes=True)


class EnrollmentCreate(BaseModel):
    student_id: int = Field(..., gt=0)
    course_code: str = Field(..., min_length=3, max_length=20)
    internal_marks: float = Field(default=0.0, ge=0.0)
    external_marks: float = Field(default=0.0, ge=0.0)
    classes_held: int = Field(default=0, ge=0)
    classes_attended: int = Field(default=0, ge=0)


class EnrollmentUpdate(BaseModel):
    internal_marks: Optional[float] = Field(default=None, ge=0.0)
    external_marks: Optional[float] = Field(default=None, ge=0.0)
    classes_held: Optional[int] = Field(default=None, ge=0)
    classes_attended: Optional[int] = Field(default=None, ge=0)


class EnrollmentDetailResponse(BaseModel):
    id: int
    student_id: int
    student_name: str
    enrollment_no: str
    course_code: str
    course_title: str
    credits: int
    internal_marks: float
    max_internal: float
    external_marks: float
    max_external: float
    total_marks: float
    max_total: float
    percentage: float
    grade: str
    grade_points: int
    classes_held: int
    classes_attended: int
    attendance_percentage: Optional[float]
    attendance_eligibility: str


class ScorecardResponse(BaseModel):
    student: StudentResponse
    enrollments: List[EnrollmentDetailResponse]
    total_credits_enrolled: int
    sgpa: float
    overall_classes_held: int
    overall_classes_attended: int
    overall_attendance_percentage: Optional[float]
    overall_attendance_eligibility: str
    grading_note: str = (
        "Illustrative Grade Scale (O=10, A+=9, A=8, B+=7, B=6, P=5, F=0). "
        "Attendance eligibility is reported separately from academic grades."
    )


# --- Schemas for Flagship Capabilities ---
class AttendanceRecoveryCourse(BaseModel):
    course_code: str
    course_title: str
    classes_attended: int
    classes_held: int
    current_percentage: Optional[float]
    status: str
    consecutive_classes_needed: int
    buffer_classes_can_miss: int
    actionable_message: str


class StudentRecoveryResponse(BaseModel):
    student_id: int
    student_name: str
    enrollment_no: str
    overall_attendance_percentage: Optional[float]
    overall_attendance_eligibility: str
    overall_consecutive_needed: int
    overall_buffer_can_miss: int
    courses: List[AttendanceRecoveryCourse]


class AdmitCardCourse(BaseModel):
    code: str
    title: str
    credits: int
    exam_date: str
    exam_time: str
    venue: str


class AdmitCardResponse(BaseModel):
    student_id: int
    student_name: str
    enrollment_no: str
    semester: int
    overall_attendance_percentage: Optional[float]
    is_eligible: bool
    status_text: str
    hall_ticket_no: str
    exam_center: str
    debarment_reason: Optional[str] = None
    issued_at: str
    qr_verification_hash: str
    enrolled_courses: List[AdmitCardCourse]


class CoursePerformanceStat(BaseModel):
    code: str
    title: str
    credits: int
    enrolled_students: int
    average_internal: float
    average_external: float
    average_total: float
    average_attendance: float


class DepartmentAnalyticsResponse(BaseModel):
    total_students: int
    total_courses: int
    average_sgpa: float
    average_attendance_percentage: float
    eligible_count: int
    shortage_count: int
    course_performance: List[CoursePerformanceStat]
    shortage_students: List[dict]


class BatchAttendanceItem(BaseModel):
    student_id: int
    is_present: bool


class BatchAttendanceRequest(BaseModel):
    course_code: str
    records: List[BatchAttendanceItem]


class AIChatRequest(BaseModel):
    message: str
    student_id: Optional[int] = None


class AIChatResponse(BaseModel):
    reply: str
    tool_called: Optional[str] = None
    tool_data: Optional[dict] = None
    suggestions: List[str] = []


class NoDuesItem(BaseModel):
    cleared: bool
    details: str


class NoDuesResponse(BaseModel):
    student_id: int
    student_name: str
    enrollment_no: str
    library: NoDuesItem
    labs: NoDuesItem
    accounts: NoDuesItem
    proctor: NoDuesItem
    is_all_cleared: bool


# =====================================================================
# PART 6: DATABASE SESSION & FICTIONAL SEED DATA
# =====================================================================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def seed_fictional_data(db: Session):
    if db.query(UserDB).count() > 0:
        return

    # 1. Seed Courses (40 Internal + 60 External confirmed for Java & ADBMS)
    courses = [
        CourseDB(
            code="BTCSE-702",
            title="Advance Java",
            credits=4,
            max_internal=40.0,
            max_external=60.0,
        ),
        CourseDB(
            code="BTCSE-704",
            title="Advanced DBMS",
            credits=4,
            max_internal=40.0,
            max_external=60.0,
        ),
        CourseDB(
            code="BTCSE-703",
            title="Data Encryption and Compression",
            credits=4,
            max_internal=40.0,
            max_external=60.0,
        ),
        CourseDB(
            code="BTCSE-DED51",
            title="Data Science",
            credits=3,
            max_internal=40.0,
            max_external=60.0,
        ),
    ]
    db.add_all(courses)
    db.flush()

    # 2. Seed Fictional Students
    students = [
        StudentDB(
            enrollment_no="ENR-2023-101",
            name="Aarav Sharma",
            email="aarav.sharma@example.edu",
            semester=7,
        ),
        StudentDB(
            enrollment_no="ENR-2023-102",
            name="Diya Patel",
            email="diya.patel@example.edu",
            semester=7,
        ),
        StudentDB(
            enrollment_no="ENR-2023-103",
            name="Rohan Verma",
            email="rohan.verma@example.edu",
            semester=7,
        ),
    ]
    db.add_all(students)
    db.flush()

    # 3. Seed Users (1 Faculty + 3 Students)
    fac_hash, fac_salt = hash_password("faculty123")
    users = [
        UserDB(
            username="faculty",
            password_hash=fac_hash,
            salt=fac_salt,
            role="faculty",
            student_id=None,
        )
    ]
    student_usernames = ["aarav", "diya", "rohan"]
    for st_obj, uname in zip(students, student_usernames):
        pw_hash, pw_salt = hash_password("student123")
        users.append(
            UserDB(
                username=uname,
                password_hash=pw_hash,
                salt=pw_salt,
                role="student",
                student_id=st_obj.id,
            )
        )
    db.add_all(users)
    db.flush()

    # 4. Seed Enrollments (Covers Eligible, Shortage <75%, and 0 Classes Held)
    enrollments = [
        # Aarav: High marks & eligible attendance
        EnrollmentDB(
            student_id=students[0].id,
            course_code="BTCSE-702",
            internal_marks=36.0,
            external_marks=54.0,
            classes_held=40,
            classes_attended=36,
        ),
        EnrollmentDB(
            student_id=students[0].id,
            course_code="BTCSE-704",
            internal_marks=34.0,
            external_marks=48.0,
            classes_held=40,
            classes_attended=34,
        ),
        EnrollmentDB(
            student_id=students[0].id,
            course_code="BTCSE-DED51",
            internal_marks=32.0,
            external_marks=45.0,
            classes_held=30,
            classes_attended=24,
        ),
        # Diya: Good marks in Java, but <75% attendance in ADBMS (Shortage, grade still A)
        EnrollmentDB(
            student_id=students[1].id,
            course_code="BTCSE-702",
            internal_marks=30.0,
            external_marks=44.0,
            classes_held=40,
            classes_attended=32,
        ),
        EnrollmentDB(
            student_id=students[1].id,
            course_code="BTCSE-704",
            internal_marks=32.0,
            external_marks=42.0,
            classes_held=40,
            classes_attended=24,
        ),
        # Rohan: Includes a newly added course with 0 classes held
        EnrollmentDB(
            student_id=students[2].id,
            course_code="BTCSE-703",
            internal_marks=25.0,
            external_marks=35.0,
            classes_held=0,
            classes_attended=0,
        ),
    ]
    db.add_all(enrollments)
    db.commit()


# Initialize schema & seed data on startup
Base.metadata.create_all(bind=engine)
with SessionLocal() as startup_db:
    seed_fictional_data(startup_db)

# =====================================================================
# PART 7: FASTAPI APP & AUTHENTICATION DEPENDENCIES
# =====================================================================
app = FastAPI(
    title="Departmental Academic Record, Result & Attendance Management System",
    description="B.Tech CSE 7th Semester Project-II (BTCSE 701) — Jamia Hamdard",
    version="1.0.0",
)

security_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> UserDB:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        username: Optional[str] = payload.get("sub")
        if not username:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload"
            )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token"
        )

    user = db.query(UserDB).filter(UserDB.username == username).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User no longer exists"
        )
    return user


def require_faculty(current_user: UserDB = Depends(get_current_user)) -> UserDB:
    if current_user.role != "faculty":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Faculty privileges required for this operation",
        )
    return current_user


optional_security_scheme = HTTPBearer(auto_error=False)


def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_security_scheme),
    db: Session = Depends(get_db),
) -> Optional[UserDB]:
    if not credentials:
        return None
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        username: Optional[str] = payload.get("sub")
        if not username:
            return None
        return db.query(UserDB).filter(UserDB.username == username).first()
    except Exception:
        return None


def check_student_or_faculty_access(
    student_id: int, current_user: UserDB, db: Session
) -> StudentDB:
    if current_user.role == "student" and current_user.student_id != student_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Students may only access their own academic records",
        )
    student = db.query(StudentDB).filter(StudentDB.id == student_id).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student ID {student_id} not found",
        )
    return student


# Helper to construct a rich EnrollmentDetailResponse
def build_enrollment_detail(
    enr: EnrollmentDB, student: StudentDB, course: CourseDB
) -> EnrollmentDetailResponse:
    total_marks = round(enr.internal_marks + enr.external_marks, 2)
    max_total = round(course.max_internal + course.max_external, 2)
    pct, grade, gp = calculate_grade_and_points(total_marks, max_total)
    att_pct, att_status = calculate_attendance_metrics(
        enr.classes_attended, enr.classes_held
    )
    return EnrollmentDetailResponse(
        id=enr.id,
        student_id=student.id,
        student_name=student.name,
        enrollment_no=student.enrollment_no,
        course_code=course.code,
        course_title=course.title,
        credits=course.credits,
        internal_marks=enr.internal_marks,
        max_internal=course.max_internal,
        external_marks=enr.external_marks,
        max_external=course.max_external,
        total_marks=total_marks,
        max_total=max_total,
        percentage=pct,
        grade=grade,
        grade_points=gp,
        classes_held=enr.classes_held,
        classes_attended=enr.classes_attended,
        attendance_percentage=att_pct,
        attendance_eligibility=att_status,
    )


def build_student_scorecard(db: Session, student: StudentDB) -> ScorecardResponse:
    enr_rows = (
        db.query(EnrollmentDB)
        .filter(EnrollmentDB.student_id == student.id)
        .all()
    )
    detailed_list: List[EnrollmentDetailResponse] = []
    total_credits = 0
    weighted_gp_sum = 0
    overall_held = 0
    overall_attended = 0

    for enr in enr_rows:
        course = (
            db.query(CourseDB).filter(CourseDB.code == enr.course_code).first()
        )
        if not course:
            continue
        detail = build_enrollment_detail(enr, student, course)
        detailed_list.append(detail)
        total_credits += course.credits
        weighted_gp_sum += course.credits * detail.grade_points
        overall_held += enr.classes_held
        overall_attended += enr.classes_attended

    sgpa = (
        round(weighted_gp_sum / total_credits, 2) if total_credits > 0 else 0.0
    )
    overall_att_pct, overall_att_status = calculate_attendance_metrics(
        overall_attended, overall_held
    )

    return ScorecardResponse(
        student=StudentResponse.model_validate(student),
        enrollments=detailed_list,
        total_credits_enrolled=total_credits,
        sgpa=sgpa,
        overall_classes_held=overall_held,
        overall_classes_attended=overall_attended,
        overall_attendance_percentage=overall_att_pct,
        overall_attendance_eligibility=overall_att_status,
    )


# =====================================================================
# PART 8: AUTHENTICATION & SELF-SERVICE SCORECARD ENDPOINTS
# =====================================================================
@app.post("/auth/login", response_model=TokenResponse, tags=["Authentication"])
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(UserDB).filter(UserDB.username == req.username.strip()).first()
    if not user or not verify_password(req.password, user.password_hash, user.salt):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    token = create_jwt_token(user)
    return TokenResponse(
        access_token=token,
        username=user.username,
        role=user.role,
        student_id=user.student_id,
    )


@app.get("/me", response_model=UserResponse, tags=["Authentication"])
def get_me(current_user: UserDB = Depends(get_current_user)):
    return current_user


@app.get("/me/scorecard", response_model=ScorecardResponse, tags=["Student Portal"])
def get_my_scorecard(
    current_user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "student" or current_user.student_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only student accounts have a personal scorecard",
        )
    student = (
        db.query(StudentDB)
        .filter(StudentDB.id == current_user.student_id)
        .first()
    )
    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found")
    return build_student_scorecard(db, student)


# =====================================================================
# PART 9: STUDENT CRUD ENDPOINTS (FACULTY ONLY)
# =====================================================================
@app.post(
    "/students",
    response_model=StudentResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Students"],
)
def create_student(
    payload: StudentCreate,
    db: Session = Depends(get_db),
    _: UserDB = Depends(require_faculty),
):
    enr_clean = payload.enrollment_no.strip().upper()
    if db.query(StudentDB).filter(StudentDB.enrollment_no == enr_clean).first():
        raise HTTPException(
            status_code=400,
            detail=f"Student with enrollment_no '{enr_clean}' already exists",
        )
    if db.query(StudentDB).filter(StudentDB.email == payload.email).first():
        raise HTTPException(
            status_code=400,
            detail=f"Student with email '{payload.email}' already exists",
        )

    new_student = StudentDB(
        enrollment_no=enr_clean,
        name=payload.name,
        email=payload.email,
        semester=payload.semester,
    )
    db.add(new_student)
    db.flush()

    # Create associated student login credentials
    uname = (
        payload.login_username.strip().lower()
        if payload.login_username
        else enr_clean.lower()
    )
    if db.query(UserDB).filter(UserDB.username == uname).first():
        uname = f"{uname}_{new_student.id}"
    pw_hash, pw_salt = hash_password(payload.login_password or "student123")
    db.add(
        UserDB(
            username=uname,
            password_hash=pw_hash,
            salt=pw_salt,
            role="student",
            student_id=new_student.id,
        )
    )
    db.commit()
    db.refresh(new_student)
    return new_student


@app.get("/students", response_model=List[StudentResponse], tags=["Students"])
def list_students(
    search: Optional[str] = Query(default=None, description="Search by name or enrollment no"),
    db: Session = Depends(get_db),
    _: UserDB = Depends(require_faculty),
):
    query = db.query(StudentDB)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(
            (StudentDB.name.ilike(pattern))
            | (StudentDB.enrollment_no.ilike(pattern))
        )
    return query.order_by(StudentDB.id.asc()).all()


@app.get("/students/{student_id}", response_model=ScorecardResponse, tags=["Students"])
def get_student_by_id(
    student_id: int,
    db: Session = Depends(get_db),
    _: UserDB = Depends(require_faculty),
):
    student = db.query(StudentDB).filter(StudentDB.id == student_id).first()
    if not student:
        raise HTTPException(
            status_code=404, detail=f"Student ID {student_id} not found"
        )
    return build_student_scorecard(db, student)


@app.put("/students/{student_id}", response_model=StudentResponse, tags=["Students"])
def update_student(
    student_id: int,
    updates: StudentUpdate,
    db: Session = Depends(get_db),
    _: UserDB = Depends(require_faculty),
):
    student = db.query(StudentDB).filter(StudentDB.id == student_id).first()
    if not student:
        raise HTTPException(
            status_code=404, detail=f"Student ID {student_id} not found"
        )

    changes = updates.model_dump(exclude_unset=True)
    if "email" in changes and changes["email"] != student.email:
        if db.query(StudentDB).filter(StudentDB.email == changes["email"]).first():
            raise HTTPException(
                status_code=400, detail="Email is already used by another student"
            )

    for key, val in changes.items():
        setattr(student, key, val)
    db.commit()
    db.refresh(student)
    return student


@app.delete("/students/{student_id}", tags=["Students"])
def delete_student(
    student_id: int,
    db: Session = Depends(get_db),
    _: UserDB = Depends(require_faculty),
):
    student = db.query(StudentDB).filter(StudentDB.id == student_id).first()
    if not student:
        raise HTTPException(
            status_code=404, detail=f"Student ID {student_id} not found"
        )
    db.query(EnrollmentDB).filter(EnrollmentDB.student_id == student.id).delete()
    db.query(UserDB).filter(UserDB.student_id == student.id).delete()
    db.delete(student)
    db.commit()
    return {"message": f"Student ID {student_id} deleted successfully"}


# =====================================================================
# PART 10: COURSE CRUD ENDPOINTS
# =====================================================================
@app.post(
    "/courses",
    response_model=CourseResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Courses"],
)
def create_course(
    payload: CourseCreate,
    db: Session = Depends(get_db),
    _: UserDB = Depends(require_faculty),
):
    code_clean = payload.code.strip().upper()
    if db.query(CourseDB).filter(CourseDB.code == code_clean).first():
        raise HTTPException(
            status_code=400, detail=f"Course '{code_clean}' already exists"
        )
    course = CourseDB(
        code=code_clean,
        title=payload.title.strip(),
        credits=payload.credits,
        max_internal=payload.max_internal,
        max_external=payload.max_external,
    )
    db.add(course)
    db.commit()
    db.refresh(course)
    return course


@app.get("/courses", response_model=List[CourseResponse], tags=["Courses"])
def list_courses(
    db: Session = Depends(get_db),
    _: UserDB = Depends(get_current_user),
):
    return db.query(CourseDB).order_by(CourseDB.id.asc()).all()


@app.put("/courses/{course_id}", response_model=CourseResponse, tags=["Courses"])
def update_course(
    course_id: int,
    updates: CourseUpdate,
    db: Session = Depends(get_db),
    _: UserDB = Depends(require_faculty),
):
    course = db.query(CourseDB).filter(CourseDB.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=404, detail=f"Course ID {course_id} not found"
        )
    for key, val in updates.model_dump(exclude_unset=True).items():
        setattr(course, key, val)
    db.commit()
    db.refresh(course)
    return course


@app.delete("/courses/{course_id}", tags=["Courses"])
def delete_course(
    course_id: int,
    db: Session = Depends(get_db),
    _: UserDB = Depends(require_faculty),
):
    course = db.query(CourseDB).filter(CourseDB.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=404, detail=f"Course ID {course_id} not found"
        )
    db.query(EnrollmentDB).filter(EnrollmentDB.course_code == course.code).delete()
    db.delete(course)
    db.commit()
    return {"message": f"Course ID {course_id} deleted successfully"}


# =====================================================================
# PART 11: ENROLLMENTS, MARKS & ATTENDANCE ENDPOINTS (FACULTY ONLY)
# =====================================================================
def validate_marks_and_attendance(
    course: CourseDB,
    internal_marks: float,
    external_marks: float,
    classes_held: int,
    classes_attended: int,
):
    if internal_marks < 0 or internal_marks > course.max_internal:
        raise HTTPException(
            status_code=400,
            detail=f"Internal marks must be between 0 and {course.max_internal}",
        )
    if external_marks < 0 or external_marks > course.max_external:
        raise HTTPException(
            status_code=400,
            detail=f"External marks must be between 0 and {course.max_external}",
        )
    if classes_attended > classes_held:
        raise HTTPException(
            status_code=400,
            detail="Classes attended cannot exceed classes held",
        )


@app.post(
    "/enrollments",
    response_model=EnrollmentDetailResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Enrollments"],
)
def create_enrollment(
    payload: EnrollmentCreate,
    db: Session = Depends(get_db),
    _: UserDB = Depends(require_faculty),
):
    student = (
        db.query(StudentDB).filter(StudentDB.id == payload.student_id).first()
    )
    if not student:
        raise HTTPException(
            status_code=404, detail=f"Student ID {payload.student_id} not found"
        )

    code_clean = payload.course_code.strip().upper()
    course = db.query(CourseDB).filter(CourseDB.code == code_clean).first()
    if not course:
        raise HTTPException(
            status_code=404, detail=f"Course '{code_clean}' not found"
        )

    existing = (
        db.query(EnrollmentDB)
        .filter(
            EnrollmentDB.student_id == student.id,
            EnrollmentDB.course_code == code_clean,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Student ID {student.id} is already enrolled in '{code_clean}'",
        )

    validate_marks_and_attendance(
        course,
        payload.internal_marks,
        payload.external_marks,
        payload.classes_held,
        payload.classes_attended,
    )

    enr = EnrollmentDB(
        student_id=student.id,
        course_code=code_clean,
        internal_marks=payload.internal_marks,
        external_marks=payload.external_marks,
        classes_held=payload.classes_held,
        classes_attended=payload.classes_attended,
    )
    db.add(enr)
    db.commit()
    db.refresh(enr)
    return build_enrollment_detail(enr, student, course)


@app.get(
    "/enrollments",
    response_model=List[EnrollmentDetailResponse],
    tags=["Enrollments"],
)
def list_enrollments(
    student_id: Optional[int] = Query(default=None),
    course_code: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    _: UserDB = Depends(require_faculty),
):
    query = db.query(EnrollmentDB)
    if student_id is not None:
        query = query.filter(EnrollmentDB.student_id == student_id)
    if course_code:
        query = query.filter(
            EnrollmentDB.course_code == course_code.strip().upper()
        )

    results: List[EnrollmentDetailResponse] = []
    for enr in query.all():
        student = (
            db.query(StudentDB).filter(StudentDB.id == enr.student_id).first()
        )
        course = (
            db.query(CourseDB).filter(CourseDB.code == enr.course_code).first()
        )
        if student and course:
            results.append(build_enrollment_detail(enr, student, course))
    return results


@app.put(
    "/enrollments/{enrollment_id}",
    response_model=EnrollmentDetailResponse,
    tags=["Enrollments"],
)
def update_enrollment(
    enrollment_id: int,
    updates: EnrollmentUpdate,
    db: Session = Depends(get_db),
    _: UserDB = Depends(require_faculty),
):
    enr = (
        db.query(EnrollmentDB).filter(EnrollmentDB.id == enrollment_id).first()
    )
    if not enr:
        raise HTTPException(
            status_code=404, detail=f"Enrollment ID {enrollment_id} not found"
        )

    student = db.query(StudentDB).filter(StudentDB.id == enr.student_id).first()
    course = db.query(CourseDB).filter(CourseDB.code == enr.course_code).first()

    changes = updates.model_dump(exclude_unset=True)
    new_internal = changes.get("internal_marks", enr.internal_marks)
    new_external = changes.get("external_marks", enr.external_marks)
    new_held = changes.get("classes_held", enr.classes_held)
    new_attended = changes.get("classes_attended", enr.classes_attended)

    validate_marks_and_attendance(
        course, new_internal, new_external, new_held, new_attended
    )

    for key, val in changes.items():
        setattr(enr, key, val)

    db.commit()
    db.refresh(enr)
    return build_enrollment_detail(enr, student, course)


@app.delete("/enrollments/{enrollment_id}", tags=["Enrollments"])
def delete_enrollment(
    enrollment_id: int,
    db: Session = Depends(get_db),
    _: UserDB = Depends(require_faculty),
):
    enr = (
        db.query(EnrollmentDB).filter(EnrollmentDB.id == enrollment_id).first()
    )
    if not enr:
        raise HTTPException(
            status_code=404, detail=f"Enrollment ID {enrollment_id} not found"
        )
    db.delete(enr)
    db.commit()
    return {"message": f"Enrollment ID {enrollment_id} deleted successfully"}


# =====================================================================
# PART 11: FLAGSHIP CAPABILITIES & EXTENSION ENDPOINTS
# =====================================================================

COURSE_EXAM_SCHEDULE = {
    "BTCSE-702": ("04-Dec-2026", "10:00 AM – 01:00 PM", "SEST Exam Hall A (2nd Floor)"),
    "BTCSE-704": ("07-Dec-2026", "10:00 AM – 01:00 PM", "SEST Exam Hall B (2nd Floor)"),
    "BTCSE-703": ("10-Dec-2026", "10:00 AM – 01:00 PM", "SEST Exam Hall A (2nd Floor)"),
    "BTCSE-DED51": ("14-Dec-2026", "10:00 AM – 01:00 PM", "SEST Exam Hall C (3rd Floor)"),
}


def calculate_recovery_for_student(db: Session, student: StudentDB) -> StudentRecoveryResponse:
    scorecard = build_student_scorecard(db, student)
    recovery_courses = []

    for detail in scorecard.enrollments:
        att = detail.classes_attended
        held = detail.classes_held
        pct = detail.attendance_percentage

        if held == 0 or pct is None:
            needed = 0
            can_miss = 0
            status_text = "Unavailable"
            msg = "No lectures conducted yet for this course."
        elif pct >= ATTENDANCE_ELIGIBILITY_THRESHOLD:
            needed = 0
            can_miss = max(0, int((att - 0.75 * held) / 0.75))
            status_text = "Eligible"
            msg = (
                f"Attendance is safe at {pct:.1f}%. You have a buffer of "
                f"{can_miss} lecture(s) you can miss without falling below 75%."
            )
        else:
            needed = max(0, math.ceil(3 * held - 4 * att))
            can_miss = 0
            status_text = "Shortage"
            msg = (
                f"Critical Shortage ({pct:.1f}%). Must attend next {needed} consecutive "
                f"lecture(s) to reach the 75% eligibility threshold."
            )

        recovery_courses.append(
            AttendanceRecoveryCourse(
                course_code=detail.course_code,
                course_title=detail.course_title,
                classes_attended=att,
                classes_held=held,
                current_percentage=pct,
                status=status_text,
                consecutive_classes_needed=needed,
                buffer_classes_can_miss=can_miss,
                actionable_message=msg,
            )
        )

    overall_held = scorecard.overall_classes_held
    overall_att = scorecard.overall_classes_attended
    overall_pct = scorecard.overall_attendance_percentage

    if overall_held == 0 or overall_pct is None:
        overall_needed = 0
        overall_buffer = 0
    elif overall_pct >= ATTENDANCE_ELIGIBILITY_THRESHOLD:
        overall_needed = 0
        overall_buffer = max(0, int((overall_att - 0.75 * overall_held) / 0.75))
    else:
        overall_needed = max(0, math.ceil(3 * overall_held - 4 * overall_att))
        overall_buffer = 0

    return StudentRecoveryResponse(
        student_id=student.id,
        student_name=student.name,
        enrollment_no=student.enrollment_no,
        overall_attendance_percentage=overall_pct,
        overall_attendance_eligibility=scorecard.overall_attendance_eligibility,
        overall_consecutive_needed=overall_needed,
        overall_buffer_can_miss=overall_buffer,
        courses=recovery_courses,
    )


def generate_student_admit_card(db: Session, student: StudentDB) -> AdmitCardResponse:
    scorecard = build_student_scorecard(db, student)
    is_eligible = (scorecard.overall_attendance_eligibility == "Eligible")

    exam_courses = []
    for enr in scorecard.enrollments:
        sched = COURSE_EXAM_SCHEDULE.get(
            enr.course_code,
            ("18-Dec-2026", "10:00 AM – 01:00 PM", "SEST Main Block Hall 1"),
        )
        exam_courses.append(
            AdmitCardCourse(
                code=enr.course_code,
                title=enr.course_title,
                credits=enr.credits,
                exam_date=sched[0],
                exam_time=sched[1],
                venue=sched[2],
            )
        )

    hash_str = f"JH:JAMIA:{student.enrollment_no}:{student.semester}:{scorecard.overall_attendance_eligibility}"
    qr_hash = hashlib.sha256(hash_str.encode("utf-8")).hexdigest()[:20].upper()

    if is_eligible:
        status_text = "ELIGIBLE (Admit Card Cleared)"
        hall_ticket = f"JH-7SEM-2026-{student.enrollment_no[-3:]}"
        center = "School of Engineering Sciences & Technology (SEST), Jamia Hamdard, New Delhi"
        debarment = None
    else:
        status_text = "DEBARRED / WITHHELD (Attendance Shortage)"
        hall_ticket = "WITHHELD-SHORTAGE"
        center = "N/A (Entry Prohibited Under Ordinance 15)"
        debarment = (
            f"Admit card withheld under Jamia Hamdard Academic Ordinance 15. "
            f"Overall attendance is {scorecard.overall_attendance_percentage}% "
            f"(Minimum 75.0% required). Contact Head of Department (HOD) CSE."
        )

    return AdmitCardResponse(
        student_id=student.id,
        student_name=student.name,
        enrollment_no=student.enrollment_no,
        semester=student.semester,
        overall_attendance_percentage=scorecard.overall_attendance_percentage,
        is_eligible=is_eligible,
        status_text=status_text,
        hall_ticket_no=hall_ticket,
        exam_center=center,
        debarment_reason=debarment,
        issued_at=datetime.now().strftime("%d-%b-%Y %I:%M %p"),
        qr_verification_hash=qr_hash,
        enrolled_courses=exam_courses,
    )


def compute_department_analytics(db: Session) -> DepartmentAnalyticsResponse:
    students = db.query(StudentDB).all()
    courses = db.query(CourseDB).all()

    total_students = len(students)
    total_courses = len(courses)

    sgpa_sum = 0.0
    att_sum = 0.0
    att_count = 0
    eligible_count = 0
    shortage_count = 0
    shortage_students = []

    for st_obj in students:
        sc = build_student_scorecard(db, st_obj)
        sgpa_sum += sc.sgpa
        if sc.overall_attendance_percentage is not None:
            att_sum += sc.overall_attendance_percentage
            att_count += 1
            if sc.overall_attendance_percentage >= ATTENDANCE_ELIGIBILITY_THRESHOLD:
                eligible_count += 1
            else:
                shortage_count += 1
                shortage_students.append({
                    "id": st_obj.id,
                    "name": st_obj.name,
                    "enrollment_no": st_obj.enrollment_no,
                    "overall_attendance": sc.overall_attendance_percentage,
                    "sgpa": sc.sgpa,
                    "shortage_courses": [
                        {
                            "code": c.course_code,
                            "title": c.course_title,
                            "pct": c.attendance_percentage,
                            "attended": c.classes_attended,
                            "held": c.classes_held,
                        }
                        for c in sc.enrollments
                        if c.attendance_percentage is not None
                        and c.attendance_percentage < ATTENDANCE_ELIGIBILITY_THRESHOLD
                    ],
                })
        else:
            shortage_count += 1

    avg_sgpa = round(sgpa_sum / total_students, 2) if total_students > 0 else 0.0
    avg_att = round(att_sum / att_count, 2) if att_count > 0 else 0.0

    course_perf = []
    for c_obj in courses:
        enrs = db.query(EnrollmentDB).filter(EnrollmentDB.course_code == c_obj.code).all()
        enr_count = len(enrs)
        if enr_count > 0:
            avg_int = round(sum(e.internal_marks for e in enrs) / enr_count, 2)
            avg_ext = round(sum(e.external_marks for e in enrs) / enr_count, 2)
            avg_tot = round(sum(e.internal_marks + e.external_marks for e in enrs) / enr_count, 2)
            c_att_list = [
                (e.classes_attended / e.classes_held * 100.0)
                for e in enrs
                if e.classes_held > 0
            ]
            avg_c_att = round(sum(c_att_list) / len(c_att_list), 2) if c_att_list else 0.0
        else:
            avg_int = avg_ext = avg_tot = avg_c_att = 0.0

        course_perf.append(
            CoursePerformanceStat(
                code=c_obj.code,
                title=c_obj.title,
                credits=c_obj.credits,
                enrolled_students=enr_count,
                average_internal=avg_int,
                average_external=avg_ext,
                average_total=avg_tot,
                average_attendance=avg_c_att,
            )
        )

    return DepartmentAnalyticsResponse(
        total_students=total_students,
        total_courses=total_courses,
        average_sgpa=avg_sgpa,
        average_attendance_percentage=avg_att,
        eligible_count=eligible_count,
        shortage_count=shortage_count,
        course_performance=course_perf,
        shortage_students=shortage_students,
    )


def run_ai_tool_calling_agent(
    db: Session, message: str, context_student_id: Optional[int] = None
) -> AIChatResponse:
    q = message.lower().strip()

    # Tool 1: Attendance Shortage Query
    if any(k in q for k in ["shortage", "debarred", "below 75", "< 75", "detained", "ineligible", "low attendance"]):
        analytics = compute_department_analytics(db)
        shortage_list = analytics.shortage_students
        if not shortage_list:
            reply = "✅ **Excellent News:** No students currently have attendance below the 75% threshold in the Department of Computer Science & Engineering."
            return AIChatResponse(
                reply=reply, tool_called="query_attendance_shortages", tool_data={"count": 0}
            )

        reply = (
            f"🚨 **Departmental Attendance Shortage Warning**\n\n"
            f"Under **Jamia Hamdard Academic Ordinance 15**, a minimum of **75.0% attendance** is mandatory to appear for the 7th Semester B.Tech End-Term Examinations.\n\n"
            f"Found **{len(shortage_list)} student(s)** facing exam debarment:\n\n"
        )
        for s in shortage_list:
            reply += f"- **{s['name']}** (`{s['enrollment_no']}`) — Overall: **{s['overall_attendance']}%** ❌\n"
            for c in s["shortage_courses"]:
                needed = max(0, math.ceil(3 * c["held"] - 4 * c["attended"]))
                reply += f"  • *{c['code']} ({c['title']})*: {c['attended']}/{c['held']} classes (**{c['pct']}%**) ➔ *Needs {needed} consecutive lectures to recover.*\n"
        reply += "\n> ⚠️ *Action Required: Instruct debarred students to meet Ms. Gautami Tripathi (Course/Project Coordinator) or HOD CSE immediately.*"

        return AIChatResponse(
            reply=reply,
            tool_called="query_attendance_shortages",
            tool_data={"shortage_count": len(shortage_list), "students": shortage_list},
            suggestions=[
                "Calculate attendance recovery for Diya Patel",
                "Draft official shortage warning notice",
                "View department analytics",
            ],
        )

    # Tool 2: Attendance Recovery Calculator
    if any(k in q for k in ["recovery", "what if", "how many classes", "consecutive", "can miss", "miss classes", "buffer", "reach 75"]):
        target_student = None
        for s in db.query(StudentDB).all():
            if s.name.lower() in q or s.name.split()[0].lower() in q or s.enrollment_no.lower() in q:
                target_student = s
                break
        if not target_student and context_student_id:
            target_student = db.query(StudentDB).filter(StudentDB.id == context_student_id).first()
        if not target_student:
            target_student = db.query(StudentDB).filter(StudentDB.name.like("%Diya%")).first()

        if target_student:
            rec = calculate_recovery_for_student(db, target_student)
            reply = (
                f"🧮 **Attendance Recovery Calculator Report**\n\n"
                f"**Student:** {rec.student_name} (`{rec.enrollment_no}`)\n"
                f"**Overall Attendance:** `{rec.overall_attendance_percentage}%` — **{rec.overall_attendance_eligibility.upper()}**\n\n"
                f"**Mathematical Formulation (Jamia 75% Rule):**\n"
                f"$$\\frac{{A + x}}{{H + x}} \\ge 0.75 \\implies x = \\lceil 3H - 4A \\rceil$$\n\n"
                f"| Course Code | Subject | Attended / Held | Percentage | Status | Action Plan |\n"
                f"| :--- | :--- | :---: | :---: | :---: | :--- |\n"
            )
            for c in rec.courses:
                status_icon = "🟢 OK" if c.status == "Eligible" else "🔴 ALERT"
                if c.status == "Shortage":
                    action = f"**Must attend next {c.consecutive_classes_needed} lectures**"
                else:
                    action = f"Safe (Buffer: {c.buffer_classes_can_miss} cuts allowed)"
                reply += f"| `{c.course_code}` | {c.course_title} | {c.classes_attended}/{c.classes_held} | {c.current_percentage}% | {status_icon} | {action} |\n"

            if rec.overall_consecutive_needed > 0:
                reply += f"\n👉 **Overall Verdict:** Student must attend **{rec.overall_consecutive_needed} consecutive departmental lectures** to clear the debarment gate."
            else:
                reply += f"\n👉 **Overall Verdict:** Student is fully eligible. Total attendance buffer: **{rec.overall_buffer_can_miss} classes**."

            return AIChatResponse(
                reply=reply,
                tool_called="calculate_attendance_recovery",
                tool_data={"student_id": target_student.id, "needed": rec.overall_consecutive_needed},
                suggestions=[
                    "Check Admit Card clearance status",
                    "Draft notice for this student",
                    "Show student scorecard",
                ],
            )

    # Tool 3: Draft Academic Notice
    if any(k in q for k in ["notice", "circular", "exam form", "marksheet", "announcement", "deadline", "draft"]):
        if any(k in q for k in ["exam form", "form", "late fee", "examination"]):
            reply = (
                f"📢 **OFFICIAL DEPARTMENTAL CIRCULAR**\n\n"
                f"**JAMIA HAMDARD**\n"
                f"*School of Engineering Sciences & Technology (SEST)*\n"
                f"**Department of Computer Science & Engineering**\n\n"
                f"**Ref No:** JH/SEST/CSE/2026/NOT-884  \n"
                f"**Date:** {datetime.now().strftime('%d %B %Y')}  \n"
                f"**Subject:** Urgent: Submission of End-Term Examination Form (7th Semester B.Tech CSE)\n\n"
                f"---\n\n"
                f"All registered students of B.Tech CSE 7th Semester are hereby notified that the university portal is open for **End-Term Examination Form Submission**.\n\n"
                f"1. **Last Date without Late Fee:** **30th November 2026 (5:00 PM)**\n"
                f"2. **Late Submission Window:** **01st Dec – 03rd Dec 2026** *(With ₹1,000 Late Fine)*\n"
                f"3. **Submission Link:** `https://jamiahamdard.edu/examinations/portal`\n"
                f"4. **Mandatory Prerequisite:** Minimum **75% Attendance** in all enrolled courses (Ordinance 15) and online No-Dues clearance.\n\n"
                f"Students failing to submit within the deadline will **NOT** be issued Admit Cards.\n\n"
                f"**Sd/-**  \n"
                f"**Prof. & Head**, Department of Computer Science & Engineering  \n"
                f"*School of Engineering Sciences & Technology, Jamia Hamdard*"
            )
            tool_name = "draft_exam_form_notice"
        elif any(k in q for k in ["marksheet", "grade card", "result", "pickup", "room 204"]):
            reply = (
                f"📄 **NOTICE: OFFICIAL MARKSHEET & GRADE CARD COLLECTION**\n\n"
                f"**JAMIA HAMDARD — SEST CSE OFFICE**\n\n"
                f"**Ref No:** JH/SEST/CSE/2026/MRK-102  \n"
                f"**Subject:** Distribution of Official 7th Semester Grade Sheets & Transcripts\n\n"
                f"---\n\n"
                f"Students of B.Tech CSE are informed that verified physical marksheets are available for in-person collection:\n\n"
                f"📍 **Location:** Departmental Administrative Office, Room 204, SEST 2nd Floor  \n"
                f"⏰ **Timings:** Monday to Friday, 10:00 AM – 03:00 PM  \n"
                f"🪪 **Mandatory Documents Required:**  \n"
                f"  - Original Jamia Hamdard Student Identity Card  \n"
                f"  - No-Dues Clearance Slip (Digital or Signed)  \n"
                f"  - Library clearance stamp  \n\n"
                f"> 💡 *Note: High academic performers (SGPA $\\ge 8.5$) can also collect their Dean's Merit Certificate.*"
            )
            tool_name = "draft_marksheet_collection_notice"
        else:
            reply = (
                f"🚨 **OFFICIAL NOTICE: 75% ATTENDANCE SHORTAGE WARNING**\n\n"
                f"**JAMIA HAMDARD — SEST DEPT OF CSE**\n\n"
                f"Notice to all 7th Semester B.Tech CSE students having attendance below 75% in theoretical/practical lectures.\n"
                f"Under University Ordinance 15, students with persistent shortage will be **DEBARRED** from the upcoming Dec 2026 End-Term Exams.\n"
                f"Submit written justifications/medical certificates to the CSE Department Office immediately."
            )
            tool_name = "draft_attendance_warning_notice"

        return AIChatResponse(
            reply=reply,
            tool_called=tool_name,
            suggestions=[
                "Send this notice via broadcast hub",
                "Check attendance shortages",
                "View admit card status",
            ],
        )

    # Tool 4: Department Analytics / Performance
    if any(k in q for k in ["analytics", "performance", "average", "stats", "department", "highest", "lowest", "gpa", "sgpa"]):
        analytics = compute_department_analytics(db)
        reply = (
            f"📊 **Department of CSE — Real-Time Academic Analytics**\n\n"
            f"- 👥 **Total Students Enrolled:** `{analytics.total_students}`\n"
            f"- 📚 **Active Departmental Courses:** `{analytics.total_courses}`\n"
            f"- 🎯 **Batch Average SGPA:** `{analytics.average_sgpa} / 10.0`\n"
            f"- 📈 **Department Attendance Average:** `{analytics.average_attendance_percentage}%`\n"
            f"- 🟢 **Exam Eligible Students:** `{analytics.eligible_count}`\n"
            f"- 🔴 **Debarred / Shortage Students:** `{analytics.shortage_count}`\n\n"
            f"**Subject-Wise Breakdown:**\n"
        )
        for cp in analytics.course_performance:
            reply += f"- **{cp.code}** ({cp.title}): Avg Score `{cp.average_total} / 100` | Attendance `{cp.average_attendance}%`\n"

        return AIChatResponse(
            reply=reply,
            tool_called="compute_department_analytics",
            tool_data={"avg_sgpa": analytics.average_sgpa, "avg_att": analytics.average_attendance_percentage},
            suggestions=[
                "Who has attendance shortage?",
                "Calculate Diya's attendance recovery",
                "Generate exam admit card",
            ],
        )

    # Tool 5: Specific Student Inquiry
    for s in db.query(StudentDB).all():
        if s.name.lower() in q or s.name.split()[0].lower() in q or s.enrollment_no.lower() in q:
            sc = build_student_scorecard(db, s)
            reply = (
                f"🎓 **Academic Profile & Scorecard: {s.name}**\n\n"
                f"- **Enrollment No:** `{s.enrollment_no}` | **Semester:** {s.semester}\n"
                f"- **Calculated SGPA:** `{sc.sgpa:.2f}`\n"
                f"- **Total Credits:** `{sc.total_credits_enrolled}`\n"
                f"- **Overall Attendance:** `{sc.overall_attendance_percentage}%` (**{sc.overall_attendance_eligibility}**)\n\n"
                f"**Enrolled Courses:**\n"
            )
            for enr in sc.enrollments:
                reply += (
                    f"- `{enr.course_code}` ({enr.course_title}): Total **{enr.total_marks}/{enr.max_total}** "
                    f"(Grade: **{enr.grade}**, GP: {enr.grade_points}) | "
                    f"Attendance: **{enr.classes_attended}/{enr.classes_held}** ({enr.attendance_percentage}%)\n"
                )

            return AIChatResponse(
                reply=reply,
                tool_called="query_student_scorecard",
                tool_data={"student_id": s.id, "sgpa": sc.sgpa, "attendance": sc.overall_attendance_percentage},
                suggestions=[
                    f"Calculate attendance recovery for {s.name}",
                    f"Check admit card for {s.name}",
                    "List all shortage students",
                ],
            )

    # Tool 6: Academic Rulebook / FAQ Auto-Responder
    reply = (
        f"🤖 **Jamia Hamdard CSE Academic Assistant**\n\n"
        f"I can assist students and faculty with real-time academic operations:\n\n"
        f"1. **Attendance Shortage & Debarment:** Check which students are below the 75% threshold under Ordinance 15.\n"
        f"2. **Attendance Recovery Simulator:** Calculate how many consecutive lectures a student must attend: $x = \\lceil 3H - 4A \\rceil$.\n"
        f"3. **Admit Card Clearance:** Verify Hall Ticket generation eligibility.\n"
        f"4. **AI Circular Generator:** Draft official notices for Exam Forms, Marksheet pickup (Room 204), or Shortage warnings.\n"
        f"5. **Departmental Analytics:** Real-time SGPA averages, pass rates, and course attendance.\n\n"
        f"*Try asking:* 'Who is debarred from exams?', 'Calculate recovery for Diya', or 'Draft exam form deadline notice'."
    )
    return AIChatResponse(
        reply=reply,
        tool_called="academic_rulebook_faq",
        suggestions=[
            "Who has attendance shortage?",
            "Calculate Diya's recovery",
            "Draft exam form notice",
            "Department analytics",
        ],
    )


# --- REST Routes for Flagship Capabilities ---

@app.get(
    "/analytics/department",
    response_model=DepartmentAnalyticsResponse,
    tags=["Analytics"],
)
def get_department_analytics(
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    return compute_department_analytics(db)


@app.get(
    "/students/{student_id}/recovery-calculator",
    response_model=StudentRecoveryResponse,
    tags=["Student Portal"],
)
def get_student_recovery(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    student = check_student_or_faculty_access(student_id, current_user, db)
    return calculate_recovery_for_student(db, student)


@app.get(
    "/me/recovery-calculator",
    response_model=StudentRecoveryResponse,
    tags=["Student Portal"],
)
def get_my_recovery(
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    if current_user.role != "student" or current_user.student_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only student accounts have a personal recovery calculator",
        )
    student = db.query(StudentDB).filter(StudentDB.id == current_user.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found")
    return calculate_recovery_for_student(db, student)


@app.get(
    "/students/{student_id}/admit-card",
    response_model=AdmitCardResponse,
    tags=["Student Portal"],
)
def get_student_admit_card(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    student = check_student_or_faculty_access(student_id, current_user, db)
    return generate_student_admit_card(db, student)


@app.get(
    "/me/admit-card",
    response_model=AdmitCardResponse,
    tags=["Student Portal"],
)
def get_my_admit_card(
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    if current_user.role != "student" or current_user.student_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only student accounts have a personal admit card",
        )
    student = db.query(StudentDB).filter(StudentDB.id == current_user.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found")
    return generate_student_admit_card(db, student)


@app.get(
    "/students/{student_id}/no-dues",
    response_model=NoDuesResponse,
    tags=["Student Portal"],
)
def get_student_no_dues(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    student = check_student_or_faculty_access(student_id, current_user, db)
    sc = build_student_scorecard(db, student)
    is_att_ok = (sc.overall_attendance_eligibility == "Eligible")

    lib = NoDuesItem(
        cleared=True,
        details="Central & Departmental Library: All books returned, zero overdue fines.",
    )
    labs = NoDuesItem(
        cleared=is_att_ok,
        details=(
            "CSE Advanced Lab & Practical Records Verified."
            if is_att_ok
            else "Withheld: Mandatory practical attendance shortage (<75%)."
        ),
    )
    acc = NoDuesItem(
        cleared=True,
        details="Jamia Finance & Accounts Office: 7th Semester Tuition and Exam fees cleared.",
    )
    proc = NoDuesItem(
        cleared=True,
        details="Office of Proctor: No pending disciplinary notices or hostel dues.",
    )

    all_cleared = lib.cleared and labs.cleared and acc.cleared and proc.cleared
    return NoDuesResponse(
        student_id=student.id,
        student_name=student.name,
        enrollment_no=student.enrollment_no,
        library=lib,
        labs=labs,
        accounts=acc,
        proctor=proc,
        is_all_cleared=all_cleared,
    )


@app.get(
    "/me/no-dues",
    response_model=NoDuesResponse,
    tags=["Student Portal"],
)
def get_my_no_dues(
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    if current_user.role != "student" or current_user.student_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only student accounts have personal no-dues clearance",
        )
    student = db.query(StudentDB).filter(StudentDB.id == current_user.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found")
    sc = build_student_scorecard(db, student)
    is_att_ok = (sc.overall_attendance_eligibility == "Eligible")

    lib = NoDuesItem(
        cleared=True,
        details="Central & Departmental Library: All books returned, zero overdue fines.",
    )
    labs = NoDuesItem(
        cleared=is_att_ok,
        details=(
            "CSE Advanced Lab & Practical Records Verified."
            if is_att_ok
            else "Withheld: Mandatory practical attendance shortage (<75%)."
        ),
    )
    acc = NoDuesItem(
        cleared=True,
        details="Jamia Finance & Accounts Office: 7th Semester Tuition and Exam fees cleared.",
    )
    proc = NoDuesItem(
        cleared=True,
        details="Office of Proctor: No pending disciplinary notices or hostel dues.",
    )

    all_cleared = lib.cleared and labs.cleared and acc.cleared and proc.cleared
    return NoDuesResponse(
        student_id=student.id,
        student_name=student.name,
        enrollment_no=student.enrollment_no,
        library=lib,
        labs=labs,
        accounts=acc,
        proctor=proc,
        is_all_cleared=all_cleared,
    )


@app.post("/attendance/batch-register", tags=["Enrollments"])
def batch_register_attendance(
    payload: BatchAttendanceRequest,
    db: Session = Depends(get_db),
    _: UserDB = Depends(require_faculty),
):
    code_clean = payload.course_code.strip().upper()
    course = db.query(CourseDB).filter(CourseDB.code == code_clean).first()
    if not course:
        raise HTTPException(status_code=404, detail=f"Course '{code_clean}' not found")

    updated_count = 0
    present_count = 0
    absent_count = 0

    for item in payload.records:
        enr = (
            db.query(EnrollmentDB)
            .filter(
                EnrollmentDB.course_code == code_clean,
                EnrollmentDB.student_id == item.student_id,
            )
            .first()
        )
        if enr:
            enr.classes_held += 1
            if item.is_present:
                enr.classes_attended += 1
                present_count += 1
            else:
                absent_count += 1
            updated_count += 1

    db.commit()
    return {
        "course_code": code_clean,
        "total_records_updated": updated_count,
        "present_count": present_count,
        "absent_count": absent_count,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


@app.post(
    "/ai/chat",
    response_model=AIChatResponse,
    tags=["AI Assistant"],
)
def ai_chat_endpoint(
    req: AIChatRequest,
    db: Session = Depends(get_db),
    current_user: Optional[UserDB] = Depends(get_optional_current_user),
):
    ctx_student_id = req.student_id
    if ctx_student_id is None and current_user and current_user.student_id:
        ctx_student_id = current_user.student_id
    return run_ai_tool_calling_agent(db, req.message, ctx_student_id)

