"""Voice verification endpoint (single-speaker clip against a subject's roster)."""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from api.auth import AuthenticatedUser, require_teacher
from api.media import read_audio_bytes
from api.ownership import assert_teacher_owns_subject
from api.schemas import VoiceVerificationResponse
from src.database.config import supabase
from src.pipelines.voice_pipeline import get_voice_embedding, identify_speaker

router = APIRouter(prefix="/api/voice", tags=["voice"])


@router.post("/verify", response_model=VoiceVerificationResponse)
async def verify_voice(
    file: UploadFile = File(..., description="Single voice clip (one speaker)"),
    subject_id: int = Form(...),
    threshold: float = Form(0.65),
    user: AuthenticatedUser = Depends(require_teacher),
):
    """
    Teacher-only (own subjects): embed the whole clip and identify the
    best-matching enrolled student (get_voice_embedding + identify_speaker
    with the original 0.65 threshold). For multi-speaker classroom audio use
    /api/attendance/analyze-voice.
    """
    assert_teacher_owns_subject(user.id, subject_id)
    audio_bytes = await read_audio_bytes(file)

    enrolled_res = (
        supabase.table("subject_students")
        .select("*, students(*)")
        .eq("subject_id", subject_id)
        .execute()
    )
    enrolled_students = enrolled_res.data or []
    if not enrolled_students:
        raise HTTPException(status_code=404, detail="No students enrolled in this course")

    candidates_dict = {
        s["students"]["student_id"]: s["students"]["voice_embedding"]
        for s in enrolled_students
        if s["students"].get("voice_embedding")
    }
    if not candidates_dict:
        raise HTTPException(
            status_code=400,
            detail="No enrolled students have voice profiles registered",
        )

    embedding = get_voice_embedding(audio_bytes)
    if embedding is None:
        raise HTTPException(status_code=400, detail="Could not process the audio clip")

    sid, score = identify_speaker(embedding, candidates_dict, threshold)

    student_name = None
    if sid is not None:
        student_name = next(
            (
                s["students"]["name"]
                for s in enrolled_students
                if s["students"]["student_id"] == sid
            ),
            None,
        )

    return VoiceVerificationResponse(
        verified=sid is not None,
        student_id=sid,
        student_name=student_name,
        score=float(score),
        threshold=threshold,
    )
