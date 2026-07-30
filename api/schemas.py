"""Request/response Pydantic models for all SnapClass API endpoints."""

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Shared entities
# ---------------------------------------------------------------------------

class StudentPublic(BaseModel):
    """Student record without the raw embedding vectors (they are large and
    should never leave the backend)."""

    model_config = ConfigDict(extra="ignore")

    student_id: int
    name: str
    has_face_embedding: bool = False
    has_voice_embedding: bool = False

    @classmethod
    def from_row(cls, row: dict) -> "StudentPublic":
        return cls(
            student_id=row["student_id"],
            name=row["name"],
            has_face_embedding=bool(row.get("face_embedding")),
            has_voice_embedding=bool(row.get("voice_embedding")),
        )


class SubjectPublic(BaseModel):
    model_config = ConfigDict(extra="ignore")

    subject_id: int
    name: str
    subject_code: Optional[str] = None
    section: Optional[str] = None
    teacher_id: Optional[int] = None


class TeacherPublic(BaseModel):
    """Teacher record without the password hash."""

    model_config = ConfigDict(extra="ignore")

    teacher_id: int
    username: str
    name: str


# ---------------------------------------------------------------------------
# Face
# ---------------------------------------------------------------------------

class FaceRecognitionResponse(BaseModel):
    """Result of one-shot face recognition (student FaceID login flow)."""

    num_faces: int
    recognized: bool
    student: Optional[StudentPublic] = None
    detected_student_ids: list[int] = []
    message: str


class RetrainResponse(BaseModel):
    success: bool
    message: str


# ---------------------------------------------------------------------------
# Voice
# ---------------------------------------------------------------------------

class VoiceVerificationResponse(BaseModel):
    """Result of verifying a single-speaker clip against a subject's enrolled
    students (identify_speaker on the whole utterance)."""

    verified: bool
    student_id: Optional[int] = None
    student_name: Optional[str] = None
    score: float
    threshold: float


# ---------------------------------------------------------------------------
# Attendance
# ---------------------------------------------------------------------------

class AttendanceResultRow(BaseModel):
    """One row of the review table shown before confirming attendance."""

    name: str
    student_id: int
    source: str
    status: str
    is_present: bool


class AttendanceLogEntry(BaseModel):
    """Shape of a row inserted into the attendance_logs table."""

    student_id: int
    subject_id: int
    timestamp: str
    is_present: bool


class FaceAttendanceAnalyzeResponse(BaseModel):
    results: list[AttendanceResultRow]
    logs: list[AttendanceLogEntry]
    detected_ids: dict[int, list[str]]
    batch_id: str
    photos_received: int
    message: Optional[str] = None


class FaceAttendanceSummaryRequest(BaseModel):
    """Summarize a server-stored batch of /analyze-face results. The server
    verifies it holds exactly expected_photos results before merging."""

    subject_id: int
    batch_id: str
    expected_photos: int


class FaceAttendanceSummaryResponse(BaseModel):
    results: list[AttendanceResultRow]
    logs: list[AttendanceLogEntry]
    detected_ids: dict[int, list[str]]
    batch_id: str
    photos_merged: int
    message: Optional[str] = None


class VoiceAttendanceAnalyzeResponse(BaseModel):
    results: list[AttendanceResultRow]
    logs: list[AttendanceLogEntry]
    detected_scores: dict[int, float]
    message: Optional[str] = None


class MarkAttendanceRequest(BaseModel):
    logs: list[AttendanceLogEntry]


class MarkAttendanceResponse(BaseModel):
    success: bool
    saved_count: int
    message: str


class AttendanceSummaryRow(BaseModel):
    """One grouped session row (mirrors the Streamlit records-table groupby)."""

    ts_group: Optional[str] = None
    time: str
    subject: Optional[str] = None
    subject_code: Optional[str] = None
    present_count: int
    total_count: int
    attendance_stats: str


class TeacherAttendanceRecordsResponse(BaseModel):
    records: list[dict[str, Any]]
    summary: list[AttendanceSummaryRow]


class StudentAttendanceResponse(BaseModel):
    logs: list[dict[str, Any]]


# ---------------------------------------------------------------------------
# Students
# ---------------------------------------------------------------------------

class StudentListResponse(BaseModel):
    students: list[StudentPublic]


class StudentRegisterResponse(BaseModel):
    student: StudentPublic
    classifier_trained: bool
    voice_enrolled: bool
    access_token: str
    token_type: str = "bearer"
    message: str


class StudentLoginResponse(BaseModel):
    student: StudentPublic
    access_token: str
    token_type: str = "bearer"
    message: str


class EnrollRequest(BaseModel):
    subject_code: str


class EnrollResponse(BaseModel):
    success: bool
    already_enrolled: bool
    subject: SubjectPublic
    message: str


class UnenrollResponse(BaseModel):
    success: bool
    message: str


class StudentSubjectStats(BaseModel):
    subject: SubjectPublic
    total: int
    attended: int


class StudentSubjectsResponse(BaseModel):
    subjects: list[StudentSubjectStats]


# ---------------------------------------------------------------------------
# Teachers
# ---------------------------------------------------------------------------

class TeacherRegisterRequest(BaseModel):
    username: str
    name: str
    password: str
    confirm_password: str


class TeacherRegisterResponse(BaseModel):
    success: bool
    message: str


class TeacherLoginRequest(BaseModel):
    username: str
    password: str


class TeacherLoginResponse(BaseModel):
    teacher: TeacherPublic
    access_token: str
    token_type: str = "bearer"


class TeacherSubject(SubjectPublic):
    total_students: int = 0
    total_classes: int = 0


class TeacherSubjectsResponse(BaseModel):
    subjects: list[TeacherSubject]


# ---------------------------------------------------------------------------
# Subjects
# ---------------------------------------------------------------------------

class SubjectCreateRequest(BaseModel):
    """teacher_id is derived from the JWT; subject_code is server-generated
    (random 8-char join code, 40 bits of entropy) — neither is accepted from
    the client."""

    name: str
    section: str


class SubjectCreateResponse(BaseModel):
    subject: SubjectPublic


class SubjectLookupResponse(BaseModel):
    subject: SubjectPublic
