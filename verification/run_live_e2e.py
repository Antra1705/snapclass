"""Live end-to-end flows against the RUNNING backend (http://localhost:8000)
and the REAL Supabase DB. Prints raw responses for every step, then cleans up
every row it created (and retrains the classifier without the test student).

Flows exercised:
  1. teacher register + login (JWT)
  2. create subject -> server-generated join code
  3. lookup of a MIGRATED code (proves migrated codes work in the live flow)
  4. student registration with a real face photo + voice clip (JWT back)
  5. enroll via the real generated join code
  6. 3-photo attendance batch -> face-summary (success)
  7. batch with one photo deliberately dropped -> expected 409
  8. real spoken-audio WAV (same PCM16 mono format the browser transcode
     produces) -> analyze-voice
  9. mark with valid logs -> saved
 10. mark including an unenrolled student -> 400 listing invalid entries,
     with proof nothing extra was written
"""

import os
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = "http://localhost:8000"
ASSETS = Path(__file__).parent / "assets"
MIGRATED_CODE = "RX65DCYF"  # 'Introduction to CS' after tonight's migration

created = {"teacher_id": None, "student_id": None, "subject_id": None}


def show(title, resp):
    body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text[:300]
    print(f"\n--- {title} -> HTTP {resp.status_code}")
    print(f"    {body}")
    return body


def main():
    c = httpx.Client(base_url=BASE, timeout=120)
    uniq = int(time.time())

    # 1. Teacher register + login
    r = c.post("/api/teachers/register", json={
        "username": f"e2e_teacher_{uniq}", "name": "E2E Teacher",
        "password": "e2e-pass-123", "confirm_password": "e2e-pass-123",
    })
    show("teacher register", r)
    r = c.post("/api/teachers/login", json={"username": f"e2e_teacher_{uniq}", "password": "e2e-pass-123"})
    body = show("teacher login", r)
    t_token = body["access_token"]
    created["teacher_id"] = body["teacher"]["teacher_id"]
    T = {"Authorization": f"Bearer {t_token}"}

    # 2. Create subject (server generates the join code)
    r = c.post("/api/subjects", json={"name": "E2E Live Subject", "section": "Z"}, headers=T)
    body = show("create subject", r)
    subject = body["subject"]
    created["subject_id"] = subject["subject_id"]
    join_code = subject["subject_code"]

    # 4. Student registration with a REAL face photo + voice clip
    with open(ASSETS / "obama.jpg", "rb") as f_img, open(ASSETS / "alice_enroll.wav", "rb") as f_wav:
        r = c.post("/api/students/register",
                   data={"name": "E2E Student"},
                   files={"face_image": ("face.jpg", f_img, "image/jpeg"),
                          "voice_audio": ("voice.wav", f_wav, "audio/wav")})
    body = show("student register (real face + voice)", r)
    s_token = body["access_token"]
    sid = body["student"]["student_id"]
    created["student_id"] = sid
    S = {"Authorization": f"Bearer {s_token}"}

    # 3. Lookup a migrated code with a real session
    r = c.get(f"/api/subjects/lookup/{MIGRATED_CODE}", headers=S)
    show(f"lookup migrated code {MIGRATED_CODE}", r)

    # 5. Enroll via the real generated join code
    r = c.post(f"/api/students/{sid}/enroll", json={"subject_code": join_code}, headers=S)
    show(f"enroll via generated code {join_code}", r)

    # 6. 3-photo batch -> face-summary (success path)
    batch_id = None
    for i, img in enumerate(["obama.jpg", "two_people.jpg", "biden.jpg"], start=1):
        with open(ASSETS / img, "rb") as f:
            data = {"subject_id": str(subject["subject_id"]), "photo_label": f"Photo {i}"}
            if batch_id:
                data["batch_id"] = batch_id
            r = c.post("/api/attendance/analyze-face", data=data,
                       files={"file": (img, f, "image/jpeg")}, headers=T)
        body = show(f"analyze-face {img}", r)
        batch_id = body["batch_id"]
    r = c.post("/api/attendance/face-summary",
               json={"subject_id": subject["subject_id"], "batch_id": batch_id, "expected_photos": 3},
               headers=T)
    body = show("face-summary (3 of 3 photos)", r)
    good_logs = body["logs"]

    # 7. Dropped-photo batch: upload 2, claim 3 -> 409
    batch_id = None
    for i, img in enumerate(["obama.jpg", "biden.jpg"], start=1):
        with open(ASSETS / img, "rb") as f:
            data = {"subject_id": str(subject["subject_id"]), "photo_label": f"Photo {i}"}
            if batch_id:
                data["batch_id"] = batch_id
            r = c.post("/api/attendance/analyze-face", data=data,
                       files={"file": (img, f, "image/jpeg")}, headers=T)
        batch_id = r.json()["batch_id"]
    r = c.post("/api/attendance/face-summary",
               json={"subject_id": subject["subject_id"], "batch_id": batch_id, "expected_photos": 3},
               headers=T)
    show("face-summary with dropped photo (2 uploaded, 3 expected)", r)

    # 8. Real spoken audio (PCM16 WAV, the browser-transcode format) -> analyze-voice
    with open(ASSETS / "bulk.wav", "rb") as f:
        r = c.post("/api/attendance/analyze-voice",
                   data={"subject_id": str(subject["subject_id"])},
                   files={"file": ("clip.wav", f, "audio/wav")}, headers=T)
    show("analyze-voice (real spoken WAV)", r)

    # 9. mark with valid logs
    r = c.post("/api/attendance/mark", json={"logs": good_logs}, headers=T)
    show("mark (valid logs)", r)

    def count_logs():
        from src.database.config import supabase
        res = supabase.table("attendance_logs").select("*").eq("subject_id", subject["subject_id"]).execute()
        return len(res.data or [])

    before = count_logs()

    # 10. mark including an unenrolled student -> 400, nothing written
    bad_logs = good_logs + [{"student_id": 999999, "subject_id": subject["subject_id"],
                             "timestamp": "2026-07-31T01:00:00", "is_present": True}]
    r = c.post("/api/attendance/mark", json={"logs": bad_logs}, headers=T)
    show("mark with unenrolled student 999999", r)
    after = count_logs()
    print(f"\n    attendance_logs rows for subject before failed mark: {before}, after: {after} "
          f"({'NOTHING written' if before == after else 'ROWS WRITTEN — BUG'})")

    # ---------------- cleanup ----------------
    print("\n=== CLEANUP ===")
    from src.database.config import supabase
    supabase.table("attendance_logs").delete().eq("subject_id", subject["subject_id"]).execute()
    supabase.table("subject_students").delete().eq("subject_id", subject["subject_id"]).execute()
    supabase.table("subjects").delete().eq("subject_id", subject["subject_id"]).execute()
    supabase.table("students").delete().eq("student_id", sid).execute()
    r = c.post("/api/face/retrain", headers=T)  # retrain WITHOUT the test student
    show("retrain classifier after removing test student", r)
    supabase.table("teachers").delete().eq("teacher_id", created["teacher_id"]).execute()
    print("    deleted: test attendance logs, enrollment, subject, student, teacher")


if __name__ == "__main__":
    main()
