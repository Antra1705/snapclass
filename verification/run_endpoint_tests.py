"""Endpoint-level verification with REAL models (dlib + Resemblyzer).

Boots the actual FastAPI app via TestClient. Supabase is replaced with an
in-memory fake (same fixture data as run_parity.py); the pipelines are real.
Verifies:
  - /api/face/recognize, /api/voice/verify, /api/attendance/analyze-face,
    /api/attendance/analyze-voice return values identical to calling the
    pipeline functions directly on the same inputs
  - JWT auth: 401 without token, 403 wrong role / wrong id / unowned subject
  - batch flow: face-summary merges server-side and 409s on missing photos

Usage: JWT_SECRET=... .venv/bin/python verification/run_endpoint_tests.py
"""

import copy
import json
import os
import re
import sys
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ASSETS = os.path.join(HERE, "assets")
sys.path.insert(0, REPO)

os.environ.setdefault("SUPABASE_URL", "https://dummy.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "dummy-key-for-verification")
os.environ.setdefault("JWT_SECRET", "verification-only-secret")

import numpy as np
from PIL import Image


def asset(name):
    return os.path.join(ASSETS, name)


def img_rgb(path):
    return np.array(Image.open(path).convert("RGB"))


def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


# ---------------------------------------------------------------------------
# Fixture data (identical to run_parity.py's synthetic DB)
# ---------------------------------------------------------------------------
import src.pipelines.face_pipeline as face_pipeline
import src.pipelines.voice_pipeline as voice_pipeline

enroll_obama = face_pipeline.get_face_embeddings(img_rgb(asset("obama.jpg")))[0]
enroll_biden = face_pipeline.get_face_embeddings(img_rgb(asset("biden.jpg")))[0]
alice_voice = voice_pipeline.get_voice_embedding(read_bytes(asset("alice_enroll.wav")))
bob_voice = voice_pipeline.get_voice_embedding(read_bytes(asset("bob_enroll.wav")))

STUDENTS = [
    {
        "student_id": 1,
        "name": "Student1-Obama/Alice",
        "face_embedding": enroll_obama.tolist(),
        "voice_embedding": alice_voice,
    },
    {
        "student_id": 2,
        "name": "Student2-Biden/Bob",
        "face_embedding": enroll_biden.tolist(),
        "voice_embedding": bob_voice,
    },
]
SUBJECTS = [
    {"subject_id": 10, "teacher_id": 100, "subject_code": "CS101", "name": "Verification 101", "section": "A"},
    {"subject_id": 99, "teacher_id": 999, "subject_code": "XX999", "name": "Someone else's subject", "section": "B"},
]
SUBJECT_STUDENTS = [
    {"subject_id": 10, "student_id": s["student_id"], "students": s} for s in STUDENTS
]
TABLES = {
    "students": STUDENTS,
    "subjects": SUBJECTS,
    "subject_students": SUBJECT_STUDENTS,
}


class FakeQuery:
    def __init__(self, rows):
        self.rows = copy.deepcopy(rows)

    def select(self, *args, **kwargs):
        return self

    def eq(self, column, value):
        self.rows = [r for r in self.rows if r.get(column) == value]
        return self

    def insert(self, data):
        self.rows = data if isinstance(data, list) else [data]
        return self

    def delete(self):
        return self

    def execute(self):
        return SimpleNamespace(data=self.rows)


class FakeSupabase:
    def __init__(self, tables):
        self.tables = tables

    def table(self, name):
        return FakeQuery(self.tables.get(name, []))


fake_supabase = FakeSupabase(TABLES)

# Patch DB access everywhere the routers/pipelines reference it.
face_pipeline.get_all_students = lambda: STUDENTS
face_pipeline.train_classifier()  # rebuild SVM on fixture students

import api.ownership as ownership
import api.routers.attendance as att_router
import api.routers.face as face_router
import api.routers.students as students_router
import api.routers.subjects as subjects_router
import api.routers.voice as voice_router

ownership.supabase = fake_supabase
att_router.supabase = fake_supabase
students_router.supabase = fake_supabase
subjects_router.supabase = fake_supabase
voice_router.supabase = fake_supabase
face_router.get_all_students = lambda: STUDENTS
students_router.get_all_students = lambda: STUDENTS

saved_attendance = []
att_router.create_attendance = lambda logs: saved_attendance.extend(logs) or logs
att_router.get_attendance_for_teacher = lambda tid: []
att_router.get_student_attendance = lambda sid: []

from fastapi.testclient import TestClient

from api.auth import create_access_token
from api.main import app

teacher_token = create_access_token(100, "teacher", "Prof. Verifier")
wrong_teacher_token = create_access_token(101, "teacher", "Other Teacher")
student1_token = create_access_token(1, "student", "Student1")
student2_token = create_access_token(2, "student", "Student2")


def auth(token):
    return {"Authorization": f"Bearer {token}"}


report = {}
failures = []


def check(name, condition, detail):
    report[name] = {"pass": bool(condition), "detail": detail}
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}: {detail}")
    if not condition:
        failures.append(name)


with TestClient(app) as client:
    # ---------------- /api/face/recognize (public) ----------------
    direct_det, _, direct_faces = face_pipeline.predict_attendance(img_rgb(asset("obama2.jpg")))
    r = client.post("/api/face/recognize", files={"file": ("obama2.jpg", read_bytes(asset("obama2.jpg")), "image/jpeg")})
    body = r.json()
    check(
        "face/recognize matches direct pipeline",
        r.status_code == 200
        and body["num_faces"] == direct_faces
        and body["recognized"] == bool(direct_det)
        and sorted(body["detected_student_ids"]) == sorted(int(k) for k in direct_det),
        f"endpoint={{num_faces: {body.get('num_faces')}, recognized: {body.get('recognized')}, "
        f"ids: {body.get('detected_student_ids')}, student: {body.get('student', {})} }} "
        f"direct={{num_faces: {direct_faces}, detected: {direct_det}}}",
    )

    r_multi = client.post("/api/face/recognize", files={"file": ("two_people.jpg", read_bytes(asset("two_people.jpg")), "image/jpeg")})
    check(
        "face/recognize rejects multi-face photo",
        r_multi.status_code == 200 and r_multi.json()["recognized"] is False and r_multi.json()["num_faces"] == 2,
        f"num_faces={r_multi.json().get('num_faces')} message={r_multi.json().get('message')!r}",
    )

    # ---------------- /api/students/login (public, issues JWT) ----------------
    r = client.post("/api/students/login", files={"file": ("obama2.jpg", read_bytes(asset("obama2.jpg")), "image/jpeg")})
    check(
        "students/login returns JWT for recognized face",
        r.status_code == 200 and r.json()["student"]["student_id"] == 1 and bool(r.json()["access_token"]),
        f"status={r.status_code} student={r.json().get('student', {}).get('student_id')}",
    )
    r = client.post("/api/students/login", files={"file": ("biden_unknown.jpg", read_bytes(asset("two_people.jpg")), "image/jpeg")})
    check("students/login 401 for non-loginable photo", r.status_code == 401, f"status={r.status_code} detail={r.json().get('detail')!r}")

    # ---------------- /api/voice/verify ----------------
    candidates = {1: alice_voice, 2: bob_voice}
    direct_emb = voice_pipeline.get_voice_embedding(read_bytes(asset("alice_probe.wav")))
    direct_sid, direct_score = voice_pipeline.identify_speaker(direct_emb, candidates, 0.65)

    r = client.post(
        "/api/voice/verify",
        files={"file": ("alice_probe.wav", read_bytes(asset("alice_probe.wav")), "audio/wav")},
        data={"subject_id": 10},
        headers=auth(teacher_token),
    )
    body = r.json()
    check(
        "voice/verify matches direct identify_speaker",
        r.status_code == 200
        and body["student_id"] == direct_sid
        and abs(body["score"] - float(direct_score)) < 1e-9
        and body["verified"] == (direct_sid is not None),
        f"endpoint=(sid {body.get('student_id')}, score {body.get('score')}) "
        f"direct=(sid {direct_sid}, score {float(direct_score)})",
    )

    r = client.post(
        "/api/voice/verify",
        files={"file": ("alice_probe.wav", read_bytes(asset("alice_probe.wav")), "audio/wav")},
        data={"subject_id": 10},
    )
    check("voice/verify 401 without token", r.status_code == 401, f"status={r.status_code}")
    r = client.post(
        "/api/voice/verify",
        files={"file": ("alice_probe.wav", read_bytes(asset("alice_probe.wav")), "audio/wav")},
        data={"subject_id": 10},
        headers=auth(student1_token),
    )
    check("voice/verify 403 for student role", r.status_code == 403, f"status={r.status_code}")
    r = client.post(
        "/api/voice/verify",
        files={"file": ("alice_probe.wav", read_bytes(asset("alice_probe.wav")), "audio/wav")},
        data={"subject_id": 99},
        headers=auth(teacher_token),
    )
    check("voice/verify 403 for unowned subject", r.status_code == 403, f"status={r.status_code}")

    # ---------------- /api/attendance/analyze-face + batch flow ----------------
    direct_p1, _, _ = face_pipeline.predict_attendance(img_rgb(asset("two_people.jpg")))
    direct_p2, _, _ = face_pipeline.predict_attendance(img_rgb(asset("biden.jpg")))

    r1 = client.post(
        "/api/attendance/analyze-face",
        files={"file": ("two_people.jpg", read_bytes(asset("two_people.jpg")), "image/jpeg")},
        data={"subject_id": 10, "photo_label": "Photo 1"},
        headers=auth(teacher_token),
    )
    b1 = r1.json()
    check(
        "analyze-face photo1 matches direct pipeline",
        r1.status_code == 200
        and sorted(int(k) for k in b1["detected_ids"]) == sorted(int(k) for k in direct_p1)
        and b1["photos_received"] == 1,
        f"endpoint detected_ids={b1.get('detected_ids')} direct={direct_p1} "
        f"results={[(row['student_id'], row['status'], row['source']) for row in b1.get('results', [])]}",
    )

    batch_id = b1["batch_id"]
    r2 = client.post(
        "/api/attendance/analyze-face",
        files={"file": ("biden.jpg", read_bytes(asset("biden.jpg")), "image/jpeg")},
        data={"subject_id": 10, "photo_label": "Photo 2", "batch_id": batch_id},
        headers=auth(teacher_token),
    )
    b2 = r2.json()
    check(
        "analyze-face photo2 joins batch",
        r2.status_code == 200 and b2["batch_id"] == batch_id and b2["photos_received"] == 2
        and sorted(int(k) for k in b2["detected_ids"]) == sorted(int(k) for k in direct_p2),
        f"photos_received={b2.get('photos_received')} detected_ids={b2.get('detected_ids')} direct={direct_p2}",
    )

    r_bad = client.post(
        "/api/attendance/face-summary",
        json={"subject_id": 10, "batch_id": batch_id, "expected_photos": 3},
        headers=auth(teacher_token),
    )
    check(
        "face-summary 409 when photos missing",
        r_bad.status_code == 409,
        f"status={r_bad.status_code} detail={r_bad.json().get('detail')!r}",
    )

    r_sum = client.post(
        "/api/attendance/face-summary",
        json={"subject_id": 10, "batch_id": batch_id, "expected_photos": 2},
        headers=auth(teacher_token),
    )
    bs = r_sum.json()
    expected_merged = {}
    for det, label in [(direct_p1, "Photo 1"), (direct_p2, "Photo 2")]:
        for sid in det:
            expected_merged.setdefault(int(sid), []).append(label)
    check(
        "face-summary merges server-side",
        r_sum.status_code == 200
        and {int(k): v for k, v in bs["detected_ids"].items()} == expected_merged
        and bs["photos_merged"] == 2,
        f"merged={bs.get('detected_ids')} expected={expected_merged} "
        f"results={[(row['student_id'], row['status'], row['source']) for row in bs.get('results', [])]}",
    )

    r_unknown = client.post(
        "/api/attendance/face-summary",
        json={"subject_id": 10, "batch_id": "nonexistent", "expected_photos": 1},
        headers=auth(teacher_token),
    )
    check("face-summary 404 unknown batch", r_unknown.status_code == 404, f"status={r_unknown.status_code}")
    r_foreign = client.post(
        "/api/attendance/face-summary",
        json={"subject_id": 10, "batch_id": batch_id, "expected_photos": 2},
        headers=auth(wrong_teacher_token),
    )
    check("face-summary 403 foreign teacher", r_foreign.status_code == 403, f"status={r_foreign.status_code}")

    # ---------------- /api/attendance/analyze-voice ----------------
    direct_bulk = voice_pipeline.process_bulk_audio(read_bytes(asset("bulk.wav")), candidates, 0.65)
    r = client.post(
        "/api/attendance/analyze-voice",
        files={"file": ("bulk.wav", read_bytes(asset("bulk.wav")), "audio/wav")},
        data={"subject_id": 10},
        headers=auth(teacher_token),
    )
    body = r.json()
    endpoint_scores = {int(k): v for k, v in body.get("detected_scores", {}).items()}
    direct_scores = {int(k): float(v) for k, v in direct_bulk.items()}
    check(
        "analyze-voice matches direct process_bulk_audio",
        r.status_code == 200
        and set(endpoint_scores) == set(direct_scores)
        and all(abs(endpoint_scores[k] - direct_scores[k]) < 1e-9 for k in direct_scores),
        f"endpoint={endpoint_scores} direct={direct_scores} "
        f"results={[(row['student_id'], row['status']) for row in body.get('results', [])]}",
    )
    r = client.post(
        "/api/attendance/analyze-voice",
        files={"file": ("bulk.wav", read_bytes(asset("bulk.wav")), "audio/wav")},
        data={"subject_id": 10},
    )
    check("analyze-voice 401 without token", r.status_code == 401, f"status={r.status_code}")

    # ---------------- /api/attendance/mark authorization ----------------
    log = {"student_id": 1, "subject_id": 10, "timestamp": "2026-07-30T22:00:00", "is_present": True}
    r = client.post("/api/attendance/mark", json={"logs": [log]}, headers=auth(teacher_token))
    check(
        "mark saves for owned subject",
        r.status_code == 200 and r.json()["saved_count"] == 1 and len(saved_attendance) == 1,
        f"status={r.status_code} saved={saved_attendance}",
    )
    bad_log = dict(log, subject_id=99)
    r = client.post("/api/attendance/mark", json={"logs": [bad_log]}, headers=auth(teacher_token))
    check("mark 403 for unowned subject", r.status_code == 403, f"status={r.status_code}")
    r = client.post("/api/attendance/mark", json={"logs": [log]}, headers=auth(student1_token))
    check("mark 403 for student role", r.status_code == 403, f"status={r.status_code}")

    # ---------------- mark: enrollment validation (atomic) ----------------
    saved_attendance.clear()
    unenrolled_log = dict(log, student_id=3)  # student 3 is not enrolled in subject 10
    r = client.post(
        "/api/attendance/mark",
        json={"logs": [log, unenrolled_log]},
        headers=auth(teacher_token),
    )
    detail = r.json().get("detail", {})
    check(
        "mark 400 for unenrolled student, nothing written",
        r.status_code == 400
        and detail.get("invalid_entries") == [{"student_id": 3, "subject_id": 10}]
        and len(saved_attendance) == 0,
        f"status={r.status_code} invalid_entries={detail.get('invalid_entries')} "
        f"records_written={len(saved_attendance)}",
    )

    # ---------------- subject codes: server-generated, client input ignored ----------------
    subjects_router.create_subject = lambda code, name, section, tid: [
        {"subject_id": 77, "subject_code": code, "name": name, "section": section, "teacher_id": tid}
    ]
    r = client.post("/api/subjects", json={"name": "New Sub", "section": "A"}, headers=auth(teacher_token))
    generated = r.json().get("subject", {}).get("subject_code", "")
    check(
        "subject create returns server-generated 8-char code",
        r.status_code == 200 and bool(re.fullmatch(r"[0-9A-HJKMNP-TV-Z]{8}", generated)),
        f"code={generated!r}",
    )
    r2 = client.post(
        "/api/subjects",
        json={"name": "New Sub", "section": "A", "subject_code": "HACK1234"},
        headers=auth(teacher_token),
    )
    check(
        "client-supplied subject_code is ignored",
        r2.status_code == 200 and r2.json()["subject"]["subject_code"] != "HACK1234",
        f"code={r2.json().get('subject', {}).get('subject_code')!r}",
    )

    # ---------------- enroll brute-force rate limit ----------------
    statuses = []
    for i in range(12):
        rr = client.post(
            "/api/students/1/enroll",
            json={"subject_code": f"WRONG{i:03d}"},
            headers=auth(student1_token),
        )
        statuses.append(rr.status_code)
    check(
        "enroll rate limited after 10 attempts/min",
        statuses[:10] == [404] * 10 and statuses[10] == 429 and statuses[11] == 429,
        f"statuses={statuses}",
    )

    # ---------------- identity-scoped record fetches ----------------
    r_own = client.get("/api/attendance/teacher/100", headers=auth(teacher_token))
    r_other = client.get("/api/attendance/teacher/100", headers=auth(wrong_teacher_token))
    check(
        "teacher records: self 200 / other 403",
        r_own.status_code == 200 and r_other.status_code == 403,
        f"self={r_own.status_code} other={r_other.status_code}",
    )
    r_own = client.get("/api/attendance/student/1", headers=auth(student1_token))
    r_other = client.get("/api/attendance/student/1", headers=auth(student2_token))
    r_teacher = client.get("/api/attendance/student/1", headers=auth(teacher_token))
    check(
        "student records: self 200 / other 403 / teacher 403",
        r_own.status_code == 200 and r_other.status_code == 403 and r_teacher.status_code == 403,
        f"self={r_own.status_code} other={r_other.status_code} teacher={r_teacher.status_code}",
    )
    r_no = client.get("/api/attendance/teacher/100")
    check("teacher records 401 without token", r_no.status_code == 401, f"status={r_no.status_code}")

with open(os.path.join(HERE, "endpoint_report.json"), "w") as f:
    json.dump(report, f, indent=2)

print(f"\n{len(report) - len(failures)}/{len(report)} checks passed")
if failures:
    print("FAILURES:", failures)
    sys.exit(1)
print("Report written to verification/endpoint_report.json")
