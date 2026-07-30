"""Student login/registration (face + optional voice) and subject management."""

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from api.auth import AuthenticatedUser, assert_self, create_access_token, require_student, require_teacher
from api.media import read_audio_bytes, read_image_rgb_np
from api.rate_limit import (
    client_ip,
    register_ip_rate_limiter,
    subject_code_ip_rate_limiter,
    subject_code_rate_limiter,
)
from api.routers.face import run_face_recognition
from api.schemas import (
    EnrollRequest,
    EnrollResponse,
    StudentListResponse,
    StudentLoginResponse,
    StudentPublic,
    StudentRegisterResponse,
    StudentSubjectStats,
    StudentSubjectsResponse,
    SubjectPublic,
    UnenrollResponse,
)
from src.database.config import supabase
from src.database.db import (
    create_student,
    enroll_student_to_subject,
    get_all_students,
    get_student_attendance,
    get_student_subjects,
    unenroll_student_to_subject,
)
from src.pipelines.face_pipeline import get_face_embeddings, train_classifier
from src.pipelines.voice_pipeline import get_voice_embedding

router = APIRouter(prefix="/api/students", tags=["students"])


@router.get("", response_model=StudentListResponse)
def list_students(user: AuthenticatedUser = Depends(require_teacher)):
    """Teacher-only: list all students (embeddings never leave the backend)."""
    students = get_all_students() or []
    return StudentListResponse(students=[StudentPublic.from_row(s) for s in students])


@router.post("/login", response_model=StudentLoginResponse)
async def login_student(file: UploadFile = File(..., description="Single face photo")):
    """Public: FaceID login. Runs the same recognition as /api/face/recognize
    and returns a student JWT when exactly one enrolled face matches."""
    image_np = await read_image_rgb_np(file)
    recognition = run_face_recognition(image_np)

    if not recognition.recognized or recognition.student is None:
        raise HTTPException(status_code=401, detail=recognition.message)

    student = recognition.student
    token = create_access_token(student.student_id, "student", student.name)
    return StudentLoginResponse(
        student=student,
        access_token=token,
        message=recognition.message,
    )


@router.post("/register", response_model=StudentRegisterResponse)
async def register_student(
    request: Request,
    name: str = Form(...),
    face_image: UploadFile = File(..., description="Single face photo (required)"),
    voice_audio: Optional[UploadFile] = File(None, description="Optional short voice clip"),
):
    """Public: create a new student profile from a face photo and an optional
    voice clip, retrain the SVM, and return a JWT (auto-login, mirroring the
    Streamlit registration flow). Per-IP rate limited so account-cycling can't
    reset the code-guessing budget."""
    register_ip_rate_limiter.check(f"register:{client_ip(request)}")

    image_np = await read_image_rgb_np(face_image)
    encodings = get_face_embeddings(image_np)
    if not encodings:
        raise HTTPException(
            status_code=400,
            detail="Couldn't detect face in the image, please try again!",
        )

    face_emb = encodings[0].tolist()

    voice_emb = None
    if voice_audio is not None:
        audio_bytes = await read_audio_bytes(voice_audio)
        voice_emb = get_voice_embedding(audio_bytes)

    response_data = create_student(name, face_embedding=face_emb, voice_embedding=voice_emb)
    if not response_data:
        raise HTTPException(status_code=500, detail="Failed to create student profile")

    classifier_trained = train_classifier()
    student = response_data[0]
    token = create_access_token(student["student_id"], "student", student["name"])

    return StudentRegisterResponse(
        student=StudentPublic.from_row(student),
        classifier_trained=classifier_trained,
        voice_enrolled=voice_emb is not None,
        access_token=token,
        message=f"Profile Created! Hi {name}!",
    )


@router.get("/{student_id}/subjects", response_model=StudentSubjectsResponse)
def student_subjects(student_id: int, user: AuthenticatedUser = Depends(require_student)):
    """Self-only: enrolled subjects with per-subject attendance stats."""
    assert_self(user, student_id)

    subjects = get_student_subjects(student_id) or []
    logs = get_student_attendance(student_id) or []

    stats_map: dict[int, dict[str, int]] = {}
    for log in logs:
        sid = log["subject_id"]
        if sid not in stats_map:
            stats_map[sid] = {"total": 0, "attended": 0}
        stats_map[sid]["total"] += 1
        if log.get("is_present"):
            stats_map[sid]["attended"] += 1

    result = []
    for sub_node in subjects:
        sub = sub_node["subjects"]
        stats = stats_map.get(sub["subject_id"], {"total": 0, "attended": 0})
        result.append(
            StudentSubjectStats(
                subject=SubjectPublic(**sub),
                total=stats["total"],
                attended=stats["attended"],
            )
        )
    return StudentSubjectsResponse(subjects=result)


@router.post("/{student_id}/enroll", response_model=EnrollResponse)
def enroll_in_subject(
    student_id: int,
    body: EnrollRequest,
    request: Request,
    user: AuthenticatedUser = Depends(require_student),
):
    """Self-only: enroll by subject join code (enroll/auto-enroll dialogs).
    Rate-limited per-user AND per-IP to block join-code brute-forcing (the
    per-IP budget survives account-cycling)."""
    assert_self(user, student_id)
    subject_code_ip_rate_limiter.check(f"code:{client_ip(request)}")
    subject_code_rate_limiter.check(f"enroll:{user.role}:{user.id}")

    res = (
        supabase.table("subjects")
        .select("subject_id, name, subject_code")
        .eq("subject_code", body.subject_code)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="Subject Code not found")

    subject = res.data[0]

    check = (
        supabase.table("subject_students")
        .select("*")
        .eq("subject_id", subject["subject_id"])
        .eq("student_id", student_id)
        .execute()
    )
    if check.data:
        return EnrollResponse(
            success=False,
            already_enrolled=True,
            subject=SubjectPublic(**subject),
            message="You are already enrolled in this program",
        )

    enroll_student_to_subject(student_id, subject["subject_id"])
    return EnrollResponse(
        success=True,
        already_enrolled=False,
        subject=SubjectPublic(**subject),
        message="Successfully enrolled!",
    )


@router.delete("/{student_id}/subjects/{subject_id}", response_model=UnenrollResponse)
def unenroll_from_subject(
    student_id: int,
    subject_id: int,
    user: AuthenticatedUser = Depends(require_student),
):
    """Self-only: unenroll from a subject."""
    assert_self(user, student_id)
    unenroll_student_to_subject(student_id, subject_id)
    return UnenrollResponse(success=True, message="Unenrolled successfully")
