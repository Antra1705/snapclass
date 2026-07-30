"""Resource-ownership checks shared by routers."""

from fastapi import HTTPException

from src.database.config import supabase


def assert_teacher_owns_subject(teacher_id: int, subject_id: int) -> None:
    res = (
        supabase.table("subjects")
        .select("subject_id")
        .eq("subject_id", subject_id)
        .eq("teacher_id", teacher_id)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=403, detail="You do not own this subject")


def assert_teacher_owns_subject_code(teacher_id: int, subject_code: str) -> None:
    res = (
        supabase.table("subjects")
        .select("subject_id")
        .eq("subject_code", subject_code)
        .eq("teacher_id", teacher_id)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=403, detail="You do not own this subject")
