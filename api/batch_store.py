"""In-memory store for multi-photo face-attendance batches.

/analyze-face records each photo's detections under a batch_id;
/face-summary merges them server-side and fails loudly if the number of
received photos does not match what the client expected. Single-process
only — a multi-worker deployment needs a shared store (e.g. Redis).
"""

import threading
import time
import uuid

_TTL_SECONDS = 15 * 60


class BatchMismatchError(Exception):
    pass


class FaceBatchStore:
    def __init__(self):
        self._lock = threading.Lock()
        self._batches: dict[str, dict] = {}

    def _purge_expired_locked(self) -> None:
        now = time.time()
        for key in [k for k, v in self._batches.items() if now - v["created_at"] > _TTL_SECONDS]:
            del self._batches[key]

    @staticmethod
    def new_batch_id() -> str:
        return uuid.uuid4().hex

    def add_photo(
        self,
        batch_id: str,
        teacher_id: int,
        subject_id: int,
        photo_label: str,
        detected_ids: dict[int, list[str]],
    ) -> int:
        """Record one photo's detections. Returns photos received so far."""
        with self._lock:
            self._purge_expired_locked()
            batch = self._batches.setdefault(
                batch_id,
                {
                    "created_at": time.time(),
                    "teacher_id": teacher_id,
                    "subject_id": subject_id,
                    "photos": [],
                },
            )
            if batch["teacher_id"] != teacher_id:
                raise BatchMismatchError("batch_id belongs to a different teacher")
            if batch["subject_id"] != subject_id:
                raise BatchMismatchError("batch_id belongs to a different subject")
            batch["photos"].append({"label": photo_label, "detected_ids": detected_ids})
            return len(batch["photos"])

    def get_batch(self, batch_id: str, teacher_id: int) -> dict | None:
        with self._lock:
            self._purge_expired_locked()
            batch = self._batches.get(batch_id)
            if batch is None:
                return None
            if batch["teacher_id"] != teacher_id:
                raise BatchMismatchError("batch_id belongs to a different teacher")
            return batch

    def merged_detected_ids(self, batch: dict) -> dict[int, list[str]]:
        merged: dict[int, list[str]] = {}
        for photo in batch["photos"]:
            for sid, labels in photo["detected_ids"].items():
                merged.setdefault(int(sid), []).extend(labels)
        return merged


face_batch_store = FaceBatchStore()
