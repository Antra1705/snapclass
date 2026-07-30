"""Subject creation, join-code lookup, and share QR generation."""

import io

import segno
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from api.auth import AuthenticatedUser, get_current_user, require_teacher
from api.ownership import assert_teacher_owns_subject_code
from api.rate_limit import client_ip, subject_code_ip_rate_limiter, subject_code_rate_limiter
from api.schemas import (
    SubjectCreateRequest,
    SubjectCreateResponse,
    SubjectLookupResponse,
    SubjectPublic,
)
from api.subject_codes import generate_subject_code
from src.database.config import supabase
from src.database.db import create_subject

router = APIRouter(prefix="/api/subjects", tags=["subjects"])


@router.post("", response_model=SubjectCreateResponse)
def create_subject_endpoint(
    body: SubjectCreateRequest,
    user: AuthenticatedUser = Depends(require_teacher),
):
    """Teacher-only: create a subject owned by the authenticated teacher.
    teacher_id comes from the JWT and subject_code is a server-generated
    random join code — the client controls neither."""
    last_error: Exception | None = None
    for _ in range(3):  # retry on the (astronomically unlikely) code collision
        code = generate_subject_code()
        try:
            data = create_subject(code, body.name, body.section, user.id)
        except Exception as e:
            last_error = e
            continue
        if data:
            return SubjectCreateResponse(subject=SubjectPublic(**data[0]))

    raise HTTPException(status_code=500, detail=f"Failed to create subject: {last_error}")


@router.get("/lookup/{subject_code}", response_model=SubjectLookupResponse)
def lookup_subject(
    subject_code: str,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Any authenticated user: find a subject by its join code (?join-code= flow).
    Rate-limited per-user AND per-IP — this endpoint confirms whether a code
    exists, so it shares the per-IP code-guessing budget with enroll."""
    subject_code_ip_rate_limiter.check(f"code:{client_ip(request)}")
    subject_code_rate_limiter.check(f"lookup:{user.role}:{user.id}")
    res = (
        supabase.table("subjects")
        .select("subject_id, name, subject_code")
        .eq("subject_code", subject_code)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="Subject Code not found")

    return SubjectLookupResponse(subject=SubjectPublic(**res.data[0]))


@router.get("/{subject_code}/qr")
def subject_join_qr(
    subject_code: str,
    base_url: str = "http://localhost:3000",
    user: AuthenticatedUser = Depends(require_teacher),
):
    """Teacher-only (own subjects): PNG QR code for the class join link."""
    assert_teacher_owns_subject_code(user.id, subject_code)

    join_url = f"{base_url}/?join-code={subject_code}"

    qr = segno.make(join_url)
    out = io.BytesIO()
    qr.save(out, kind="png", scale=10, border=1)

    return Response(content=out.getvalue(), media_type="image/png")
