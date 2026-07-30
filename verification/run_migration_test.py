"""Verify the subject-code migration: regenerate codes for existing subjects,
then confirm lookup/enroll work with the NEW codes and that pre-existing
enrollments are unaffected.

Uses a stateful in-memory fake of the supabase client (updates persist), so
the migration's writes are visible to the subsequent endpoint calls.

Usage: JWT_SECRET=... .venv/bin/python verification/run_migration_test.py
"""

import copy
import os
import sys
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)

os.environ.setdefault("SUPABASE_URL", "https://dummy.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "dummy-key-for-verification")
os.environ.setdefault("JWT_SECRET", "verification-only-secret-0123456789ab")


# ---------------------------------------------------------------------------
# Stateful fake supabase (select / eq / insert / update all mutate the store)
# ---------------------------------------------------------------------------
class StatefulQuery:
    def __init__(self, rows: list):
        self._rows = rows  # live reference to the backing list
        self._filters: list[tuple[str, object]] = []
        self._update: dict | None = None
        self._insert = None

    def select(self, *args, **kwargs):
        return self

    def eq(self, column, value):
        self._filters.append((column, value))
        return self

    def update(self, data: dict):
        self._update = data
        return self

    def insert(self, data):
        self._insert = data
        return self

    def _matches(self, row):
        return all(row.get(c) == v for c, v in self._filters)

    def execute(self):
        if self._insert is not None:
            new_rows = self._insert if isinstance(self._insert, list) else [self._insert]
            self._rows.extend(new_rows)
            return SimpleNamespace(data=copy.deepcopy(new_rows))
        if self._update is not None:
            changed = []
            for row in self._rows:
                if self._matches(row):
                    row.update(self._update)
                    changed.append(row)
            return SimpleNamespace(data=copy.deepcopy(changed))
        return SimpleNamespace(data=copy.deepcopy([r for r in self._rows if self._matches(r)]))


class StatefulSupabase:
    def __init__(self, tables):
        self.tables = tables

    def table(self, name):
        return StatefulQuery(self.tables.setdefault(name, []))


STUDENTS = [
    {"student_id": 1, "name": "Already Enrolled", "face_embedding": None, "voice_embedding": None},
    {"student_id": 2, "name": "New Joiner", "face_embedding": None, "voice_embedding": None},
]
SUBJECTS = [
    {"subject_id": 10, "teacher_id": 100, "subject_code": "CS101", "name": "Intro CS", "section": "A"},
    {"subject_id": 11, "teacher_id": 100, "subject_code": "MATH101", "name": "Calculus", "section": "B"},
]
# Student 1 is ALREADY enrolled in subject 10 before the migration.
SUBJECT_STUDENTS = [
    {"subject_id": 10, "student_id": 1, "students": STUDENTS[0]},
]
TABLES = {"students": STUDENTS, "subjects": SUBJECTS, "subject_students": SUBJECT_STUDENTS}
fake = StatefulSupabase(TABLES)

import api.ownership as ownership
import api.routers.attendance as att_router
import api.routers.students as students_router
import api.routers.subjects as subjects_router
import src.pipelines.face_pipeline as face_pipeline

face_pipeline.get_all_students = lambda: STUDENTS
ownership.supabase = fake
students_router.supabase = fake
subjects_router.supabase = fake
att_router.supabase = fake

# enroll writes go through the fake so the new enrollment persists
students_router.enroll_student_to_subject = lambda sid, subid: fake.table("subject_students").insert(
    {"subject_id": subid, "student_id": sid}
).execute().data
att_router.create_attendance = lambda logs: logs

from fastapi.testclient import TestClient

from api.auth import create_access_token
from api.main import app
from scripts.migrate_subject_codes import regenerate_all_codes

failures = []


def check(name, condition, detail):
    print(f"[{'PASS' if condition else 'FAIL'}] {name}: {detail}")
    if not condition:
        failures.append(name)


print("== BEFORE migration: existing codes ==")
old_codes = {s["subject_id"]: s["subject_code"] for s in TABLES["subjects"]}
print(f"  {old_codes}")

mapping = regenerate_all_codes(fake)
print("\n== migration mapping ==")
for m in mapping:
    print(f"  subject_id={m['subject_id']}: {m['old_code']!r} -> {m['new_code']!r}")

new_by_id = {m["subject_id"]: m["new_code"] for m in mapping}
import re

check(
    "all new codes are 8-char base32 and unique",
    all(re.fullmatch(r"[0-9A-HJKMNP-TV-Z]{8}", m["new_code"]) for m in mapping)
    and len({m["new_code"] for m in mapping}) == len(mapping),
    f"new_codes={[m['new_code'] for m in mapping]}",
)
check(
    "DB rows now hold the new codes",
    {s["subject_id"]: s["subject_code"] for s in TABLES["subjects"]} == new_by_id,
    f"subjects table codes={ {s['subject_id']: s['subject_code'] for s in TABLES['subjects']} }",
)

student2 = {"Authorization": f"Bearer {create_access_token(2, 'student', 'New Joiner')}"}
teacher = {"Authorization": f"Bearer {create_access_token(100, 'teacher', 'T')}"}

with TestClient(app) as client:
    # Old code no longer resolves
    r_old = client.get(f"/api/subjects/lookup/CS101", headers=student2)
    check("lookup by OLD code now 404", r_old.status_code == 404, f"status={r_old.status_code}")

    # New code resolves to the right subject
    new10 = new_by_id[10]
    r_new = client.get(f"/api/subjects/lookup/{new10}", headers=student2)
    check(
        "lookup by NEW code resolves to subject 10",
        r_new.status_code == 200 and r_new.json()["subject"]["subject_id"] == 10,
        f"status={r_new.status_code} subject={r_new.json().get('subject')}",
    )

    # Existing enrollment (student 1 in subject 10) is intact: enrolling student 1
    # again via the new code should report already-enrolled.
    student1 = {"Authorization": f"Bearer {create_access_token(1, 'student', 'Already Enrolled')}"}
    r_dup = client.post("/api/students/1/enroll", json={"subject_code": new10}, headers=student1)
    check(
        "pre-existing enrollment survives migration (already-enrolled via new code)",
        r_dup.status_code == 200 and r_dup.json()["already_enrolled"] is True,
        f"status={r_dup.status_code} body={r_dup.json()}",
    )

    # A new student can enroll using the new code
    r_join = client.post("/api/students/2/enroll", json={"subject_code": new10}, headers=student2)
    enrolled_now = [
        (e["subject_id"], e["student_id"]) for e in TABLES["subject_students"]
    ]
    check(
        "new student enrolls via new code",
        r_join.status_code == 200
        and r_join.json()["success"] is True
        and (10, 2) in enrolled_now,
        f"status={r_join.status_code} enrollments={enrolled_now}",
    )

    # Attendance for the already-enrolled student still validates (enrollment
    # is keyed by id, not by code, so the code change doesn't affect it).
    att_router.get_attendance_for_teacher = lambda tid: []
    log = {"student_id": 1, "subject_id": 10, "timestamp": "2026-07-30T22:00:00", "is_present": True}
    r_mark = client.post("/api/attendance/mark", json={"logs": [log]}, headers=teacher)
    check(
        "mark still works for already-enrolled student after migration",
        r_mark.status_code == 200 and r_mark.json()["saved_count"] == 1,
        f"status={r_mark.status_code} body={r_mark.json()}",
    )

print(f"\n{5 - len(failures)}/5 checks passed" if not failures else f"\nFAILURES: {failures}")
sys.exit(1 if failures else 0)
