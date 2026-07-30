# ClassSnap — Frontend

Next.js (App Router, TypeScript, Tailwind) frontend for the ClassSnap biometric
attendance system. Talks to the FastAPI backend in the parent repo.

## Setup

```bash
npm install
cp .env.example .env.local   # already present after clone of this folder
npm run dev                  # http://localhost:3000
```

The backend must be running (default `http://localhost:8000`) with CORS enabled
for `http://localhost:3000` (already configured in the FastAPI app).

### Pointing at a deployed backend

Change **one** value in `.env.local`:

```
NEXT_PUBLIC_API_BASE_URL=https://your-backend.onrender.com
```

`src/lib/config.ts` is the only place this is read.

## Structure

- `src/lib/config.ts` — backend base URL (single source of truth)
- `src/lib/types.ts` — TS mirrors of the backend Pydantic schemas
- `src/lib/api.ts` — fetch wrapper: attaches `Authorization: Bearer <token>`,
  parses FastAPI `{detail}` errors into `ApiError` (401/403/429 + the
  structured `/api/attendance/mark` 400)
- `src/lib/endpoints.ts` — one typed function per backend endpoint
- `src/lib/auth.tsx` — auth context (localStorage JWT), global 401 → login redirect,
  `useRequireRole` route guard
- `src/components/CameraCapture.tsx` — getUserMedia + canvas single-frame snapshot
  (with `<input capture="user">` fallback), discrete capture → preview → confirm
- `src/components/VoiceRecorder.tsx` — MediaRecorder fixed clip, transcoded to
  WAV client-side (`src/lib/wav.ts`) so the backend's librosa can decode it
- `src/components/AddPhotosDialog.tsx` — face attendance: per-photo
  `analyze-face` into a server batch → `face-summary` (server verifies photo
  count) → review → `mark`
- `src/components/VoiceAttendanceDialog.tsx` — voice attendance:
  record → `analyze-voice` → review → `mark`

## Pages

| Route | Who | What |
|---|---|---|
| `/` | public | role picker; forwards `?join-code=` from QR links |
| `/teacher/register`, `/teacher/login` | public | username/password auth |
| `/teacher/dashboard` | teacher | tabs: Take Attendance (face/voice dialogs), Manage Subjects (create → shows generated join code + QR, share), Attendance Records (filter by subject) |
| `/student/register` | public | name + face capture + optional voice enrollment |
| `/student/login` | public | FaceID login (401 → prompt to register) |
| `/student/dashboard` | student | enrolled subjects w/ stats, enroll-by-code dialog (auto-opens from `?join-code=`), unenroll, attendance history |

## Auth notes

The JWT is stored in `localStorage` and attached as `Authorization: Bearer` by
the fetch wrapper. httpOnly cookies were not used because the backend returns
the token in the JSON body (no `Set-Cookie`) — switching would require a
backend change.
