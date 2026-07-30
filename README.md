# SnapClass — AI Biometric Attendance

SnapClass takes classroom attendance with **face recognition** (a teacher snaps a few
classroom photos) and **voice recognition** (students say "I am present" into one
recording). Students log in with their face — no passwords — and enroll in subjects
with a join code or QR link.

The project has three parts:

| Part | Tech | Where |
|---|---|---|
| **Backend API** | FastAPI + dlib/SVM + Resemblyzer + Supabase | `api/`, `src/`, `main.py` |
| **Frontend** | Next.js (App Router, TypeScript, Tailwind) | `classsnap-frontend/` |
| **Legacy app** | The original Streamlit UI (kept for reference) | `app.py`, `src/screens/`, `src/components/` |

The FastAPI backend was extracted from the Streamlit app **without changing any model
inference logic** — the Streamlit app still runs, but the Next.js frontend + API is the
current stack.

---

## How the biometrics work

### Face recognition (`src/pipelines/face_pipeline.py`)

1. **Detection + embedding** — dlib detects every face in a photo and produces a
   128-dimension face embedding per face.
2. **Classification** — a linear SVM (`SVC(kernel='linear', probability=True,
   class_weight='balanced')`) is trained on the embeddings of every registered student
   (stored in Supabase). It is retrained automatically whenever a student registers.
3. **Acceptance check** — a prediction only counts if the claimed student's stored
   embedding is actually close to the probe (distance threshold `0.4`), which stops the
   SVM from force-assigning unknown faces to the nearest student.

The trained classifier lives **in memory** (module-level singleton) — there is no model
file on disk; it is rebuilt from the DB at startup and on retrain.

### Voice recognition (`src/pipelines/voice_pipeline.py`)

1. Audio is loaded at 16 kHz (`librosa`), and **Resemblyzer** produces a speaker
   embedding (d-vector).
2. For attendance, the clip is split into voiced segments and each segment is compared
   (cosine similarity) against the voice embeddings of the subject's enrolled students.
3. A student is marked present if their best similarity ≥ **0.65** (configurable per
   request).

Students record an optional voice sample at registration; without it they simply can't
use voice attendance.

---

## Repository layout

```
snapclass/
├── main.py                  # uvicorn entrypoint for the API
├── api/                     # FastAPI backend
│   ├── main.py              # app, CORS, startup (model warm-up, JWT check)
│   ├── auth.py              # JWT creation/validation, role dependencies
│   ├── schemas.py           # Pydantic request/response models (the API contract)
│   ├── media.py             # multipart image/audio decoding
│   ├── batch_store.py       # server-side multi-photo batch store (TTL, thread-safe)
│   ├── rate_limit.py        # fixed-window per-user + per-IP rate limiters
│   ├── subject_codes.py     # secrets-based join-code generation
│   ├── ownership.py         # teacher-owns-subject checks
│   └── routers/             # face, voice, attendance, students, teachers, subjects
├── src/
│   ├── pipelines/           # face_pipeline.py, voice_pipeline.py (model inference)
│   ├── database/            # Supabase client (config.py) + queries (db.py)
│   ├── screens/, components/, ui/   # legacy Streamlit UI
├── classsnap-frontend/      # Next.js frontend (has its own README)
├── scripts/
│   └── migrate_subject_codes.py     # one-off: regenerate join codes for old subjects
├── verification/            # proof scripts (see "Verification" below)
└── app.py                   # legacy Streamlit entrypoint
```

---

## Setup & running

### Prerequisites

- **Python 3.12** (dlib/torch wheels are not available for 3.13+)
- **Node 18+** / npm
- A **Supabase** project with tables: `teachers`, `students`, `subjects`,
  `subject_students`, `attendance_logs`

### 1. Backend

```bash
# create the venv (Python 3.12!) and install deps
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt

# secrets — create .streamlit/secrets.toml (gitignored):
#   SUPABASE_URL = "https://<project-ref>.supabase.co"
#   SUPABASE_KEY = "<secret key>"          # server-side key
#   JWT_SECRET   = "<64 hex chars>"        # e.g. openssl rand -hex 32
# (environment variables with the same names take priority if set)

.venv/bin/uvicorn api.main:app --reload --port 8000
```

Startup **fails fast** if Supabase credentials or `JWT_SECRET` are missing. The face
and voice models are warmed up during startup (takes a few seconds).

### 2. Frontend

```bash
cd classsnap-frontend
npm install
npm run dev          # http://localhost:3000
```

The backend URL lives in one place: `NEXT_PUBLIC_API_BASE_URL` in
`classsnap-frontend/.env.local` (defaults to `http://localhost:8000`). Deploying the
backend elsewhere (e.g. Render) is a one-line change there.

---

## Using the app

**Teacher:** register with username/password → login → *Manage Subjects* → create a
subject (a random join code + QR is generated) → share it → *Take Attendance*: add a
few classroom photos → *Run Face Analysis* → review the present/absent table → *Confirm
& Save*. Or *Use Voice Attendance*: record the class saying "I am present" → analyze →
confirm. *Attendance Records* shows per-session summaries.

**Student:** open the student portal → capture a face photo to log in. Unknown face →
inline registration (name + optional voice sample). Enroll in a subject by typing the
join code, or by scanning the teacher's QR (the link auto-opens the enroll dialog).
The dashboard shows enrolled subjects with attended/total stats and full history.

---

## API overview

All responses are JSON; errors use FastAPI's `{"detail": ...}` envelope. Auth is a
`Authorization: Bearer <JWT>` header. Roles: **public**, **teacher**, **student**,
**self-only** (the id in the path must match the token).

| Endpoint | Method | Auth | Purpose |
|---|---|---|---|
| `/api/health` | GET | public | liveness check |
| `/api/teachers/register` | POST | public | create teacher account |
| `/api/teachers/login` | POST | public | password login → JWT |
| `/api/teachers/{id}/subjects` | GET | self-only | teacher's subjects + stats |
| `/api/students/register` | POST | public (IP rate-limited) | face photo (+ optional voice) → account + JWT |
| `/api/students/login` | POST | public | FaceID login → JWT (401 if unrecognized) |
| `/api/students` | GET | teacher | list students |
| `/api/students/{id}/subjects` | GET | self-only | enrolled subjects + attendance stats |
| `/api/students/{id}/enroll` | POST | self-only (rate-limited) | enroll by join code |
| `/api/students/{id}/subjects/{sid}` | DELETE | self-only | unenroll |
| `/api/subjects` | POST | teacher | create subject (server generates the join code) |
| `/api/subjects/lookup/{code}` | GET | any auth (rate-limited) | resolve a join code |
| `/api/subjects/{code}/qr` | GET | teacher (owner) | join-link QR as PNG |
| `/api/face/recognize` | POST | public | one-shot face recognition |
| `/api/face/retrain` | POST | teacher | retrain the SVM |
| `/api/voice/verify` | POST | teacher (owner) | single-speaker voice check |
| `/api/attendance/analyze-face` | POST | teacher (owner) | analyze one photo into a batch |
| `/api/attendance/face-summary` | POST | teacher (owner) | merge a photo batch (409 if incomplete) |
| `/api/attendance/analyze-voice` | POST | teacher (owner) | bulk voice attendance |
| `/api/attendance/mark` | POST | teacher (owner) | persist attendance logs |
| `/api/attendance/teacher/{id}` | GET | self-only | records + per-session summary |
| `/api/attendance/student/{id}` | GET | self-only | own attendance history |

### The multi-photo attendance flow (important)

The frontend calls `analyze-face` once per photo. The **first** response returns a
`batch_id`; subsequent photos are uploaded with it. `face-summary` is then called with
`expected_photos` — the server verifies it actually holds that many results and returns
**409 Conflict** if any upload was dropped, so a network failure can never silently
produce wrong attendance. Detections are merged server-side and returned with `logs`
ready for `POST /api/attendance/mark`.

`mark` re-validates that **every** `(student, subject)` pair is enrolled; if any isn't,
it returns **400** with the offending entries and writes **nothing**.

---

## Security model

- **JWT auth (HS256)** — tokens carry `{sub, role, name}`, expire after 24 h
  (`JWT_EXPIRES_MINUTES`), signed with `JWT_SECRET`.
- **Join codes** are server-generated: 8 chars from a 32-char alphabet ≈ **40 bits of
  entropy** (~1.1 × 10¹² combinations). Clients cannot choose codes.
- **Rate limiting** (in-memory fixed window): enroll 10/min per user **and** 20/min per
  IP; code lookup 20/min per IP; student registration 5/min per IP — so an attacker
  can't reset budgets by cycling fresh accounts.
- Embedding vectors **never leave the backend**; API responses only expose booleans
  like `has_face_embedding`.
- Secrets live in `.streamlit/secrets.toml` (gitignored) or environment variables.

---

## Verification & maintenance scripts

Everything security- or correctness-critical has a runnable proof in `verification/`:

| Script | Proves |
|---|---|
| `run_parity.py` | new pipelines produce bit-identical results to the original Streamlit code |
| `run_endpoint_tests.py` | endpoint behavior with real models (TestClient + fake DB) |
| `run_mark_enrollment_test.py` | unenrolled students reject the whole `mark` request |
| `run_account_cycling_test.py` | per-IP limits survive account cycling |
| `run_migration_test.py` | the join-code migration logic |
| `run_live_e2e.py` | full flows against a **running** backend + real DB (registers real test data, then cleans it up) |

`scripts/migrate_subject_codes.py [--dry-run]` regenerates join codes for subjects
created before the random-code scheme (already run against the production DB).

---

## Troubleshooting

- **`RuntimeError: SUPABASE_URL and SUPABASE_KEY must be set`** — create
  `.streamlit/secrets.toml` (see Setup).
- **`RuntimeError: JWT_SECRET must be set`** — add `JWT_SECRET` to the same file.
- **dlib/torch install failures** — you're probably on Python 3.13+; use 3.12.
- **Voice always absent** — the clip must be a format `librosa` can read (the frontend
  transcodes recordings to PCM WAV in the browser for exactly this reason), and the
  students need voice embeddings from registration.
- **Sessions died after a backend restart** — `JWT_SECRET` changed; keep it stable in
  `secrets.toml`.
