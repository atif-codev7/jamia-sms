import hashlib
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
