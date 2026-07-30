"""Attendance analysis, marking, and record fetch endpoints."""

from datetime import datetime
from typing import Callable, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from api.auth import AuthenticatedUser, assert_self, require_student, require_teacher
from api.batch_store import BatchMismatchError, face_batch_store
from api.media import read_audio_bytes, read_image_rgb_np
from api.ownership import assert_teacher_owns_subject
from api.schemas import (
    AttendanceLogEntry,
    AttendanceResultRow,
    AttendanceSummaryRow,
    FaceAttendanceAnalyzeResponse,
    FaceAttendanceSummaryRequest,
    FaceAttendanceSummaryResponse,
    MarkAttendanceRequest,
    MarkAttendanceResponse,
    StudentAttendanceResponse,
    TeacherAttendanceRecordsResponse,
    VoiceAttendanceAnalyzeResponse,
)
from src.database.config import supabase
from src.database.db import create_attendance, get_attendance_for_teacher, get_student_attendance
from src.pipelines.face_pipeline import predict_attendance
from src.pipelines.voice_pipeline import process_bulk_audio

router = APIRouter(prefix="/api/attendance", tags=["attendance"])


def _fetch_enrolled(subject_id: int) -> list[dict]:
    enrolled_res = (
        supabase.table("subject_students")
        .select("*, students(*)")
        .eq("subject_id", subject_id)
        .execute()
    )
    return enrolled_res.data or []


def _build_results_and_logs(
    enrolled_students: list[dict],
    subject_id: int,
    presence_of: Callable[[dict], tuple[bool, str]],
) -> tuple[list[AttendanceResultRow], list[AttendanceLogEntry]]:
    """Build the review rows + insertable logs for a roster, given a function
    that decides (is_present, source_label) per student. Mirrors the loops in
    teacher_tab_take_attendance and voice_attendance_dialog."""
    results: list[AttendanceResultRow] = []
    logs: list[AttendanceLogEntry] = []
    current_timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    for node in enrolled_students:
        student = node["students"]
        is_present, source = presence_of(student)

        results.append(
            AttendanceResultRow(
                name=student["name"],
                student_id=student["student_id"],
                source=source,
                status="Present" if is_present else "Absent",
                is_present=bool(is_present),
            )
        )
        logs.append(
            AttendanceLogEntry(
                student_id=student["student_id"],
                subject_id=subject_id,
                timestamp=current_timestamp,
                is_present=bool(is_present),
            )
        )

    return results, logs


def _face_presence(detected_ids: dict[int, list[str]]) -> Callable[[dict], tuple[bool, str]]:
    def presence_of(student: dict) -> tuple[bool, str]:
        sources = detected_ids.get(int(student["student_id"]), [])
        is_present = len(sources) > 0
        return is_present, ", ".join(sources) if is_present else "-"

    return presence_of


@router.post("/analyze-face", response_model=FaceAttendanceAnalyzeResponse)
async def analyze_face_attendance(
    file: UploadFile = File(..., description="Single classroom photo"),
    subject_id: int = Form(...),
    photo_label: str = Form("Photo 1", description="Label used in Source column (e.g. Photo 1)"),
    batch_id: Optional[str] = Form(
        None,
        description="Pass the batch_id from the first photo's response on subsequent photos",
    ),
    user: AuthenticatedUser = Depends(require_teacher),
):
    """
    Teacher-only (own subjects): one-shot face attendance for a single
    classroom photo. Detections are also stored server-side under batch_id so
    /face-summary can merge multiple photos verifiably. Nothing is persisted —
    call POST /mark to save.
    """
    assert_teacher_owns_subject(user.id, subject_id)

    image_np = await read_image_rgb_np(file)
    detected, _, _ = predict_attendance(image_np)

    photo_detected_ids: dict[int, list[str]] = {}
    if detected:
        for sid in detected.keys():
            photo_detected_ids.setdefault(int(sid), []).append(photo_label)

    if batch_id is None:
        batch_id = face_batch_store.new_batch_id()
    try:
        photos_received = face_batch_store.add_photo(
            batch_id, user.id, subject_id, photo_label, photo_detected_ids
        )
    except BatchMismatchError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e

    enrolled_students = _fetch_enrolled(subject_id)
    if not enrolled_students:
        return FaceAttendanceAnalyzeResponse(
            results=[],
            logs=[],
            detected_ids=photo_detected_ids,
            batch_id=batch_id,
            photos_received=photos_received,
            message="No students enrolled in this course",
        )

    results, logs = _build_results_and_logs(
        enrolled_students, subject_id, _face_presence(photo_detected_ids)
    )
    return FaceAttendanceAnalyzeResponse(
        results=results,
        logs=logs,
        detected_ids=photo_detected_ids,
        batch_id=batch_id,
        photos_received=photos_received,
    )


@router.post("/face-summary", response_model=FaceAttendanceSummaryResponse)
def summarize_face_attendance(
    body: FaceAttendanceSummaryRequest,
    user: AuthenticatedUser = Depends(require_teacher),
):
    """
    Teacher-only (own subjects): merge a server-stored batch of /analyze-face
    results. Fails with 409 if the server did not receive exactly
    expected_photos results (e.g. a dropped request), instead of silently
    producing incomplete attendance.
    """
    assert_teacher_owns_subject(user.id, body.subject_id)

    try:
        batch = face_batch_store.get_batch(body.batch_id, user.id)
    except BatchMismatchError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e

    if batch is None:
        raise HTTPException(
            status_code=404,
            detail="Unknown or expired batch_id — re-run /analyze-face for all photos",
        )
    if batch["subject_id"] != body.subject_id:
        raise HTTPException(status_code=403, detail="batch_id belongs to a different subject")

    received = len(batch["photos"])
    if received != body.expected_photos:
        received_labels = [p["label"] for p in batch["photos"]]
        raise HTTPException(
            status_code=409,
            detail=(
                f"Batch incomplete: expected {body.expected_photos} photos but the server "
                f"received {received} ({received_labels}). Re-upload the missing photos "
                "with the same batch_id before summarizing."
            ),
        )

    merged_detected_ids = face_batch_store.merged_detected_ids(batch)

    enrolled_students = _fetch_enrolled(body.subject_id)
    if not enrolled_students:
        return FaceAttendanceSummaryResponse(
            results=[],
            logs=[],
            detected_ids=merged_detected_ids,
            batch_id=body.batch_id,
            photos_merged=received,
            message="No students enrolled in this course",
        )

    results, logs = _build_results_and_logs(
        enrolled_students, body.subject_id, _face_presence(merged_detected_ids)
    )
    return FaceAttendanceSummaryResponse(
        results=results,
        logs=logs,
        detected_ids=merged_detected_ids,
        batch_id=body.batch_id,
        photos_merged=received,
    )


@router.post("/analyze-voice", response_model=VoiceAttendanceAnalyzeResponse)
async def analyze_voice_attendance(
    file: UploadFile = File(..., description="Single classroom audio clip"),
    subject_id: int = Form(...),
    threshold: float = Form(0.65),
    user: AuthenticatedUser = Depends(require_teacher),
):
    """
    Teacher-only (own subjects): one-shot voice attendance for a single audio
    clip. Mirrors voice_attendance_dialog + process_bulk_audio.
    Does not persist — call POST /mark to save.
    """
    assert_teacher_owns_subject(user.id, subject_id)

    audio_bytes = await read_audio_bytes(file)
    enrolled_students = _fetch_enrolled(subject_id)

    if not enrolled_students:
        return VoiceAttendanceAnalyzeResponse(
            results=[],
            logs=[],
            detected_scores={},
            message="No students enrolled in this course",
        )

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

    detected_scores_raw = process_bulk_audio(audio_bytes, candidates_dict, threshold=threshold)
    detected_scores = {int(k): float(v) for k, v in detected_scores_raw.items()}

    def presence_of(student: dict) -> tuple[bool, str]:
        score = detected_scores.get(int(student["student_id"]), 0.0)
        is_present = bool(score > 0)
        return is_present, "Present" if is_present else "-"

    results, logs = _build_results_and_logs(enrolled_students, subject_id, presence_of)
    return VoiceAttendanceAnalyzeResponse(
        results=results,
        logs=logs,
        detected_scores=detected_scores,
    )


@router.post("/mark", response_model=MarkAttendanceResponse)
def mark_attendance(
    body: MarkAttendanceRequest,
    user: AuthenticatedUser = Depends(require_teacher),
):
    """Teacher-only (own subjects): persist attendance logs. Every subject_id
    in the payload must belong to the authenticated teacher, and every
    (student_id, subject_id) pair must exist in subject_students. Any invalid
    entry rejects the WHOLE request — nothing is partially written."""
    if not body.logs:
        raise HTTPException(status_code=400, detail="No attendance logs provided")

    subject_ids = {log.subject_id for log in body.logs}
    for subject_id in subject_ids:
        assert_teacher_owns_subject(user.id, subject_id)

    enrolled_pairs: set[tuple[int, int]] = set()
    for subject_id in subject_ids:
        res = (
            supabase.table("subject_students")
            .select("student_id")
            .eq("subject_id", subject_id)
            .execute()
        )
        for row in res.data or []:
            enrolled_pairs.add((int(row["student_id"]), subject_id))

    invalid_entries = [
        {"student_id": log.student_id, "subject_id": log.subject_id}
        for log in body.logs
        if (log.student_id, log.subject_id) not in enrolled_pairs
    ]
    if invalid_entries:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Some entries reference students not enrolled in the subject; "
                "nothing was written",
                "invalid_entries": invalid_entries,
            },
        )

    payload = [log.model_dump() for log in body.logs]
    try:
        saved = create_attendance(payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {e}") from e

    return MarkAttendanceResponse(
        success=True,
        saved_count=len(saved) if saved else len(payload),
        message="Attendance taken",
    )


@router.get("/teacher/{teacher_id}", response_model=TeacherAttendanceRecordsResponse)
def get_teacher_attendance_records(
    teacher_id: int,
    user: AuthenticatedUser = Depends(require_teacher),
):
    """Self-only: fetch and summarize attendance records for a teacher,
    grouped per session like the Streamlit attendance_records tab."""
    assert_self(user, teacher_id)
    records = get_attendance_for_teacher(teacher_id) or []

    groups: dict[tuple, dict] = {}
    for r in records:
        ts = r.get("timestamp")
        subjects = r.get("subjects") or {}
        ts_group = ts.split(".")[0] if ts else None
        time_label = datetime.fromisoformat(ts).strftime("%Y-%m-%d %I:%M %p") if ts else "N/A"
        key = (ts_group, time_label, subjects.get("name"), subjects.get("subject_code"))

        if key not in groups:
            groups[key] = {
                "ts_group": ts_group,
                "time": time_label,
                "subject": subjects.get("name"),
                "subject_code": subjects.get("subject_code"),
                "present_count": 0,
                "total_count": 0,
            }
        groups[key]["total_count"] += 1
        if bool(r.get("is_present", False)):
            groups[key]["present_count"] += 1

    summary = [
        AttendanceSummaryRow(
            **g,
            attendance_stats=f"{g['present_count']} / {g['total_count']} Students",
        )
        for g in groups.values()
    ]
    summary.sort(key=lambda x: x.ts_group or "", reverse=True)

    return TeacherAttendanceRecordsResponse(records=records, summary=summary)


@router.get("/student/{student_id}", response_model=StudentAttendanceResponse)
def get_student_attendance_records(
    student_id: int,
    user: AuthenticatedUser = Depends(require_student),
):
    """Self-only: a student's own attendance logs."""
    assert_self(user, student_id)
    logs = get_student_attendance(student_id) or []
    return StudentAttendanceResponse(logs=logs)
