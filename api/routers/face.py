"""Face recognition endpoints (recognition probe + classifier retraining)."""

import numpy as np
from fastapi import APIRouter, Depends, File, UploadFile

from api.auth import AuthenticatedUser, require_teacher
from api.media import read_image_rgb_np
from api.schemas import FaceRecognitionResponse, RetrainResponse, StudentPublic
from src.database.db import get_all_students
from src.pipelines.face_pipeline import predict_attendance, train_classifier

router = APIRouter(prefix="/api/face", tags=["face"])


def run_face_recognition(image_np: np.ndarray) -> FaceRecognitionResponse:
    """Single-face recognition mirroring the Streamlit FaceID login flow.
    Shared by POST /api/face/recognize and POST /api/students/login."""
    detected, _, num_faces = predict_attendance(image_np)
    detected_ids = [int(sid) for sid in detected.keys()]

    if num_faces == 0:
        return FaceRecognitionResponse(
            num_faces=0,
            recognized=False,
            detected_student_ids=detected_ids,
            message="Face not found",
        )

    if num_faces > 1:
        return FaceRecognitionResponse(
            num_faces=num_faces,
            recognized=False,
            detected_student_ids=detected_ids,
            message="Multiple faces detected, please ensure only your face is visible",
        )

    if detected:
        student_id = list(detected.keys())[0]
        all_students = get_all_students()
        student = next(
            (s for s in all_students if int(s["student_id"]) == student_id),
            None,
        )
        if student:
            return FaceRecognitionResponse(
                num_faces=num_faces,
                recognized=True,
                student=StudentPublic.from_row(student),
                detected_student_ids=detected_ids,
                message=f"Welcome Back, {student['name']}!",
            )

    return FaceRecognitionResponse(
        num_faces=num_faces,
        recognized=False,
        detected_student_ids=detected_ids,
        message="Face not recognized, You might be a new student!",
    )


@router.post("/recognize", response_model=FaceRecognitionResponse)
async def recognize_face(file: UploadFile = File(..., description="Single face photo")):
    """Public: recognition probe used by the login/registration screen to tell
    a returning student from a new one. Issues no token — use
    POST /api/students/login to authenticate."""
    image_np = await read_image_rgb_np(file)
    return run_face_recognition(image_np)


@router.post("/retrain", response_model=RetrainResponse)
def retrain_classifier(user: AuthenticatedUser = Depends(require_teacher)):
    """Teacher-only: rebuild the SVM from current student embeddings."""
    success = train_classifier()
    return RetrainResponse(
        success=success,
        message="Classifier retrained" if success else "No students with face embeddings to train on",
    )
