"""SnapClass FastAPI application.

Run with: uvicorn api.main:app --reload  (or python main.py)
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.auth import ensure_jwt_secret_configured
from api.routers import attendance, face, students, subjects, teachers, voice
from src.pipelines.face_pipeline import get_trained_model, load_dlib_models
from src.pipelines.voice_pipeline import load_voice_encoder


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_jwt_secret_configured()
    # Warm all model singletons once at startup (replaces st.cache_resource):
    # dlib detector/shape-predictor/face-rec weights, the Resemblyzer voice
    # encoder, and the SVM trained on current student embeddings.
    load_dlib_models()
    load_voice_encoder()
    get_trained_model()
    yield


app = FastAPI(
    title="SnapClass API",
    description="Biometric attendance backend (dlib/SVM face recognition + Resemblyzer voice verification)",
    version="1.0.0",
    lifespan=lifespan,
)

# Comma-separated list of allowed frontend origins. Defaults to the local
# Next.js dev server; in production set e.g.
#   FRONTEND_ORIGINS=https://snapclass.vercel.app
_origins = [
    o.strip()
    for o in os.environ.get("FRONTEND_ORIGINS", "http://localhost:3000").split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(face.router)
app.include_router(voice.router)
app.include_router(attendance.router)
app.include_router(students.router)
app.include_router(teachers.router)
app.include_router(subjects.router)


@app.get("/api/health", tags=["health"])
def health():
    return {"status": "ok"}
