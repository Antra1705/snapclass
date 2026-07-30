# Hugging Face Spaces (Docker SDK) — SnapClass FastAPI backend
# Space must listen on 0.0.0.0:7860
# https://huggingface.co/docs/hub/spaces-sdks-docker

FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=7860

# System libs for dlib wheels, OpenCV-ish deps, and librosa/ffmpeg audio decode
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# CPU-only PyTorch first (avoids the huge CUDA wheel that OOMs free hosts)
COPY requirements-api.txt .
RUN pip install --upgrade pip \
    && pip install torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install -r requirements-api.txt

# App code only (see .dockerignore)
COPY api/ api/
COPY src/ src/
COPY main.py .

EXPOSE 7860

# HF Spaces health-checks this port; fall back to $PORT if overridden
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
