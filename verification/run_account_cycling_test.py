"""Before/after test for the account-cycling bypass of code-guess throttling.

Attack: from a single IP, register a fresh student every time the per-user
enroll budget (10/min) is exhausted, so the attacker keeps guessing join codes
at full speed. This works when only per-user rate limiting exists.

BEFORE = per-user limiter only (IP limiters effectively disabled).
AFTER  = per-user + per-IP enroll/lookup limiter + per-IP register limiter.

Both phases run the SAME attack loop in-process; only the injected limiters
differ. Registration's face pipeline is stubbed (this test is about rate
limiting, not recognition).

Usage: JWT_SECRET=... .venv/bin/python verification/run_account_cycling_test.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ASSETS = os.path.join(HERE, "assets")
sys.path.insert(0, REPO)

os.environ.setdefault("SUPABASE_URL", "https://dummy.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "dummy-key-for-verification")
os.environ.setdefault("JWT_SECRET", "verification-only-secret-0123456789ab")

import copy
from types import SimpleNamespace

import numpy as np

import api.ownership as ownership
import api.routers.students as students_router
import api.routers.subjects as subjects_router
import src.pipelines.face_pipeline as face_pipeline
from api.rate_limit import FixedWindowRateLimiter

face_pipeline.get_all_students = lambda: []


# Fake DB: no subject matches any guessed code, so every enroll attempt that
# reaches the DB returns 404 (the throttling, not the lookup, is under test).
class FakeQuery:
    def __init__(self, rows):
        self.rows = copy.deepcopy(rows)

    def select(self, *a, **k):
        return self

    def eq(self, c, v):
        self.rows = [r for r in self.rows if r.get(c) == v]
        return self

    def execute(self):
        return SimpleNamespace(data=self.rows)


class FakeSupabase:
    def table(self, name):
        return FakeQuery([])


fake = FakeSupabase()
ownership.supabase = fake
students_router.supabase = fake
subjects_router.supabase = fake

# Stub the registration pipeline (recognition is out of scope here).
_next_id = {"v": 1000}


def _fake_create_student(name, face_embedding=None, voice_embedding=None):
    _next_id["v"] += 1
    return [{"student_id": _next_id["v"], "name": name, "face_embedding": None, "voice_embedding": None}]


students_router.get_face_embeddings = lambda img: [np.zeros(128)]
students_router.create_student = _fake_create_student
students_router.train_classifier = lambda: True
students_router.get_voice_embedding = lambda b: None

from fastapi.testclient import TestClient

from api.main import app

ATTACKER_IP = {"X-Forwarded-For": "203.0.113.7"}
ROUNDS = 8
GUESSES_PER_ACCOUNT = 12  # attacker tries until per-user 429


def inject_limiters(per_user, ip_code, ip_register):
    students_router.subject_code_rate_limiter = per_user
    subjects_router.subject_code_rate_limiter = per_user
    students_router.subject_code_ip_rate_limiter = ip_code
    subjects_router.subject_code_ip_rate_limiter = ip_code
    students_router.register_ip_rate_limiter = ip_register


def run_attack(client):
    with open(os.path.join(ASSETS, "obama2.jpg"), "rb") as f:
        img_bytes = f.read()

    accounts_created = 0
    register_throttled = 0
    real_guesses = 0  # enroll calls that reached logic (200/404), i.e. NOT throttled

    for rnd in range(ROUNDS):
        r = client.post(
            "/api/students/register",
            data={"name": f"attacker{rnd}"},
            files={"face_image": ("f.jpg", img_bytes, "image/jpeg")},
            headers=ATTACKER_IP,
        )
        if r.status_code == 429:
            register_throttled += 1
            continue
        accounts_created += 1
        token = r.json()["access_token"]
        sid = r.json()["student"]["student_id"]
        headers = {**ATTACKER_IP, "Authorization": f"Bearer {token}"}

        for g in range(GUESSES_PER_ACCOUNT):
            rr = client.post(
                f"/api/students/{sid}/enroll",
                json={"subject_code": f"GUESS{rnd}{g:02d}"},
                headers=headers,
            )
            if rr.status_code == 429:
                break
            real_guesses += 1

    return {
        "accounts_created": accounts_created,
        "register_throttled": register_throttled,
        "effective_code_guesses": real_guesses,
    }


with TestClient(app) as client:
    UNLIMITED = FixedWindowRateLimiter(max_requests=10**9, window_seconds=60)

    print("== BEFORE (per-user limiter only; IP limiting absent) ==")
    inject_limiters(
        per_user=FixedWindowRateLimiter(10, 60),
        ip_code=UNLIMITED,
        ip_register=UNLIMITED,
    )
    before = run_attack(client)
    print(before)

    print("\n== AFTER (per-user 10/min + per-IP code 20/min + per-IP register 5/min) ==")
    inject_limiters(
        per_user=FixedWindowRateLimiter(10, 60),
        ip_code=FixedWindowRateLimiter(20, 60),
        ip_register=FixedWindowRateLimiter(5, 60),
    )
    after = run_attack(client)
    print(after)

    ok = (
        before["effective_code_guesses"] > after["effective_code_guesses"]
        and after["effective_code_guesses"] <= 20
        and after["accounts_created"] <= 5
        and after["register_throttled"] > 0
    )
    print(f"\nAccount-cycling throttled: {ok}")
    print(
        f"  code guesses: before={before['effective_code_guesses']} "
        f"after={after['effective_code_guesses']}"
    )
    print(
        f"  accounts minted: before={before['accounts_created']} "
        f"after={after['accounts_created']} (register 429s after: {after['register_throttled']})"
    )
    sys.exit(0 if ok else 1)
