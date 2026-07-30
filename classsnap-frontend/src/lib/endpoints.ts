/**
 * One function per backend endpoint. Pages call these instead of building URLs
 * or FormData inline, so request/response shapes live in exactly one place.
 */
import { apiBlob, apiFetch } from "./api";
import type {
  EnrollResponse,
  FaceAttendanceAnalyzeResponse,
  FaceAttendanceSummaryResponse,
  FaceRecognitionResponse,
  MarkAttendanceResponse,
  AttendanceLogEntry,
  RetrainResponse,
  StudentAttendanceResponse,
  StudentListResponse,
  StudentLoginResponse,
  StudentRegisterResponse,
  StudentSubjectsResponse,
  SubjectCreateResponse,
  SubjectLookupResponse,
  TeacherAttendanceRecordsResponse,
  TeacherLoginResponse,
  TeacherRegisterResponse,
  TeacherSubjectsResponse,
  UnenrollResponse,
  VoiceAttendanceAnalyzeResponse,
  VoiceVerificationResponse,
} from "./types";

// ---------------- Teachers (auth) ----------------
export function teacherRegister(body: {
  username: string;
  name: string;
  password: string;
  confirm_password: string;
}) {
  return apiFetch<TeacherRegisterResponse>("/api/teachers/register", {
    json: body,
    auth: false,
  });
}

export function teacherLogin(body: { username: string; password: string }) {
  return apiFetch<TeacherLoginResponse>("/api/teachers/login", {
    json: body,
    auth: false,
  });
}

export function teacherSubjects(teacherId: number) {
  return apiFetch<TeacherSubjectsResponse>(`/api/teachers/${teacherId}/subjects`);
}

// ---------------- Students (auth) ----------------
export function studentRegister(name: string, faceImage: Blob, voiceAudio?: Blob | null) {
  const form = new FormData();
  form.append("name", name);
  form.append("face_image", faceImage, "face.jpg");
  if (voiceAudio) form.append("voice_audio", voiceAudio, "voice.webm");
  return apiFetch<StudentRegisterResponse>("/api/students/register", {
    form,
    auth: false,
  });
}

export function studentLogin(faceImage: Blob) {
  const form = new FormData();
  form.append("file", faceImage, "face.jpg");
  return apiFetch<StudentLoginResponse>("/api/students/login", { form, auth: false });
}

export function listStudents() {
  return apiFetch<StudentListResponse>("/api/students");
}

export function studentSubjects(studentId: number) {
  return apiFetch<StudentSubjectsResponse>(`/api/students/${studentId}/subjects`);
}

export function studentEnroll(studentId: number, subjectCode: string) {
  return apiFetch<EnrollResponse>(`/api/students/${studentId}/enroll`, {
    json: { subject_code: subjectCode },
  });
}

export function studentUnenroll(studentId: number, subjectId: number) {
  return apiFetch<UnenrollResponse>(`/api/students/${studentId}/subjects/${subjectId}`, {
    method: "DELETE",
  });
}

export function studentAttendance(studentId: number) {
  return apiFetch<StudentAttendanceResponse>(`/api/attendance/student/${studentId}`);
}

// ---------------- Subjects ----------------
export function createSubject(body: { name: string; section: string }) {
  return apiFetch<SubjectCreateResponse>("/api/subjects", { json: body });
}

export function lookupSubject(subjectCode: string) {
  return apiFetch<SubjectLookupResponse>(
    `/api/subjects/lookup/${encodeURIComponent(subjectCode)}`
  );
}

/** QR PNG for the class join link. Auth is required, so we fetch it as a blob. */
export function subjectQrBlob(subjectCode: string, baseUrl: string) {
  return apiBlob(`/api/subjects/${encodeURIComponent(subjectCode)}/qr`, {
    query: { base_url: baseUrl },
  });
}

// ---------------- Face ----------------
export function recognizeFace(faceImage: Blob) {
  const form = new FormData();
  form.append("file", faceImage, "face.jpg");
  return apiFetch<FaceRecognitionResponse>("/api/face/recognize", { form, auth: false });
}

export function retrainClassifier() {
  return apiFetch<RetrainResponse>("/api/face/retrain", { method: "POST" });
}

// ---------------- Attendance: face ----------------
export function analyzeFace(params: {
  file: Blob;
  subjectId: number;
  photoLabel: string;
  batchId?: string;
}) {
  const form = new FormData();
  form.append("file", params.file, "photo.jpg");
  form.append("subject_id", String(params.subjectId));
  form.append("photo_label", params.photoLabel);
  if (params.batchId) form.append("batch_id", params.batchId);
  return apiFetch<FaceAttendanceAnalyzeResponse>("/api/attendance/analyze-face", { form });
}

export function faceSummary(body: {
  subject_id: number;
  batch_id: string;
  expected_photos: number;
}) {
  return apiFetch<FaceAttendanceSummaryResponse>("/api/attendance/face-summary", { json: body });
}

// ---------------- Attendance: voice ----------------
export function analyzeVoice(params: { file: Blob; subjectId: number; threshold?: number }) {
  const form = new FormData();
  form.append("file", params.file, "audio.webm");
  form.append("subject_id", String(params.subjectId));
  if (params.threshold !== undefined) form.append("threshold", String(params.threshold));
  return apiFetch<VoiceAttendanceAnalyzeResponse>("/api/attendance/analyze-voice", { form });
}

export function verifyVoice(params: { file: Blob; subjectId: number; threshold?: number }) {
  const form = new FormData();
  form.append("file", params.file, "audio.webm");
  form.append("subject_id", String(params.subjectId));
  if (params.threshold !== undefined) form.append("threshold", String(params.threshold));
  return apiFetch<VoiceVerificationResponse>("/api/voice/verify", { form });
}

// ---------------- Attendance: mark + records ----------------
export function markAttendance(logs: AttendanceLogEntry[]) {
  return apiFetch<MarkAttendanceResponse>("/api/attendance/mark", { json: { logs } });
}

export function teacherAttendanceRecords(teacherId: number) {
  return apiFetch<TeacherAttendanceRecordsResponse>(`/api/attendance/teacher/${teacherId}`);
}
