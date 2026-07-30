"""Teacher registration, login (returns JWT), and subject listing."""

from fastapi import APIRouter, Depends, HTTPException

from api.auth import AuthenticatedUser, assert_self, create_access_token, require_teacher
from api.schemas import (
    TeacherLoginRequest,
    TeacherLoginResponse,
    TeacherPublic,
    TeacherRegisterRequest,
    TeacherRegisterResponse,
    TeacherSubject,
    TeacherSubjectsResponse,
)
from src.database.db import (
    check_teacher_exists,
    create_teacher,
    get_teacher_subjects,
    teacher_login,
)

router = APIRouter(prefix="/api/teachers", tags=["teachers"])


@router.post("/register", response_model=TeacherRegisterResponse)
def register_teacher(body: TeacherRegisterRequest):
    """Public: mirrors the Streamlit register_teacher validation exactly."""
    if not body.username or not body.password or not body.name:
        raise HTTPException(status_code=400, detail="All fields are required!")
    if check_teacher_exists(body.username):
        raise HTTPException(status_code=400, detail="Username already taken!")
    if body.password != body.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match!")

    try:
        create_teacher(body.username, body.password, body.name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {e}") from e

    return TeacherRegisterResponse(
        success=True,
        message="Successfully Registered! Please login now.",
    )


@router.post("/login", response_model=TeacherLoginResponse)
def login_teacher(body: TeacherLoginRequest):
    """Public: password login, returns a teacher JWT."""
    if not body.username or not body.password:
        raise HTTPException(status_code=401, detail="Invalid username or password!")

    teacher = teacher_login(body.username, body.password)
    if not teacher:
        raise HTTPException(status_code=401, detail="Invalid username or password!")

    token = create_access_token(teacher["teacher_id"], "teacher", teacher["name"])
    return TeacherLoginResponse(teacher=TeacherPublic(**teacher), access_token=token)


@router.get("/{teacher_id}/subjects", response_model=TeacherSubjectsResponse)
def teacher_subjects(teacher_id: int, user: AuthenticatedUser = Depends(require_teacher)):
    """Self-only: subjects with total_students / total_classes stats."""
    assert_self(user, teacher_id)
    subjects = get_teacher_subjects(teacher_id) or []
    return TeacherSubjectsResponse(subjects=[TeacherSubject(**s) for s in subjects])
