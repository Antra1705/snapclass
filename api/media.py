"""Helpers to decode one-shot multipart uploads into the exact input types the
pipelines expect (RGB numpy arrays for faces, raw bytes for audio)."""

import io

import numpy as np
from fastapi import HTTPException, UploadFile
from PIL import Image


async def read_image_rgb_np(file: UploadFile) -> np.ndarray:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty image file")
    try:
        img = Image.open(io.BytesIO(data))
        # Same preprocessing as the Streamlit teacher flow: np.array(img.convert('RGB'))
        return np.array(img.convert("RGB"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not decode image: {e}") from e


async def read_audio_bytes(file: UploadFile) -> bytes:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty audio file")
    return data
