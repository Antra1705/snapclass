"""Before/after test for /api/attendance/mark enrollment validation.

Posts a batch where one log entry references a student NOT enrolled in the
subject. Before the fix this is accepted and written; after the fix the whole
request must be rejected with 400 and nothing written.

Also measures raw guess throughput against POST /api/students/{id}/enroll
(wrong subject codes) to quantify brute-force feasibility.

Usage: JWT_SECRET=... .venv/bin/python verification/run_mark_enrollment_test.py
"""

import copy
import os
import secrets
import sys
import time
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)

os.environ.setdefault("SUPABASE_URL", "https://dummy.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "dummy-key-for-verification")
os.environ.setdefault("JWT_SECRET", "verification-only-secret-0123456789ab")

# Roster: students 1 and 2 enrolled in subject 10. Student 3 exists but is NOT enrolled.
STUDENTS = [
    {"student_id": 1, "name": "Enrolled One", "face_embedding": None, "voice_embedding": None},
    {"student_id": 2, "name": "Enrolled Two", "face_embedding": None, "voice_embedding": None},
    {"student_id": 3, "name": "NOT Enrolled", "face_embedding": None, "voice_embedding": None},
]
SUBJECTS = [
    {"subject_id": 10, "teacher_id": 100, "subject_code": "CS101", "name": "Verification 101", "section": "A"},
]
SUBJECT_STUDENTS = [
    {"subject_id": 10, "student_id": 1, "students": STUDENTS[0]},
    {"subject_id": 10, "student_id": 2, "students": STUDENTS[1]},
]
TABLES = {"students": STUDENTS, "subjects": SUBJECTS, "subject_students": SUBJECT_STUDENTS}


class FakeQuery:
    def __init__(self, rows):
        self.rows = copy.deepcopy(rows)

    def select(self, *args, **kwargs):
        return self

    def eq(self, column, value):
        self.rows = [r for r in self.rows if r.get(column) == value]
        return self

    def execute(self):
        return SimpleNamespace(data=self.rows)


class FakeSupabase:
    def __init__(self, tables):
        self.tables = tables

    def table(self, name):
        return FakeQuery(self.tables.get(name, []))


fake_supabase = FakeSupabase(TABLES)

import src.pipelines.face_pipeline as face_pipeline

face_pipeline.get_all_students = lambda: []

import api.ownership as ownership
import api.routers.attendance as att_router
import api.routers.students as students_router

ownership.supabase = fake_supabase
att_router.supabase = fake_supabase
students_router.supabase = fake_supabase

saved_attendance = []
att_router.create_attendance = lambda logs: saved_attendance.extend(logs) or logs
students_router.enroll_student_to_subject = lambda sid, subid: None

from fastapi.testclient import TestClient

from api.auth import create_access_token
from api.main import app

teacher_token = {"Authorization": f"Bearer {create_access_token(100, 'teacher', 'T')}"}
student1_token = {"Authorization": f"Bearer {create_access_token(1, 'student', 'S1')}"}

with TestClient(app) as client:
    print("== /api/attendance/mark with one UNENROLLED student in the batch ==")
    logs = [
        {"student_id": 1, "subject_id": 10, "timestamp": "2026-07-30T22:00:00", "is_present": True},
        {"student_id": 3, "subject_id": 10, "timestamp": "2026-07-30T22:00:00", "is_present": True},
    ]
    r = client.post("/api/attendance/mark", json={"logs": logs}, headers=teacher_token)
    print(f"status: {r.status_code}")
    print(f"response: {r.json()}")
    print(f"records written: {len(saved_attendance)} -> {saved_attendance}")

    print("\n== enroll brute-force throughput (100 wrong-code guesses, no artificial delay) ==")
    start = time.perf_counter()
    n = 100
    codes_tried = 0
    last_status = None
    for _ in range(n):
        code = "".join(secrets.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ") for _ in range(2)) + str(secrets.randbelow(1000)).zfill(3)
        resp = client.post("/api/students/1/enroll", json={"subject_code": code}, headers=student1_token)
        last_status = resp.status_code
        codes_tried += 1
        if resp.status_code == 429:
            break
    elapsed = time.perf_counter() - start
    print(f"codes tried: {codes_tried} in {elapsed:.2f}s -> {codes_tried / elapsed:.0f} guesses/sec (last status: {last_status})")
