/**
 * TypeScript mirrors of the backend Pydantic schemas (api/schemas.py).
 * Field names and shapes match the FastAPI responses exactly — do not add
 * fields the backend does not return.
 */

export type Role = "teacher" | "student";

export interface StudentPublic {
  student_id: number;
  name: string;
  has_face_embedding: boolean;
  has_voice_embedding: boolean;
}

export interface SubjectPublic {
  subject_id: number;
  name: string;
  subject_code: string | null;
  section: string | null;
  teacher_id: number | null;
}

export interface TeacherPublic {
  teacher_id: number;
  username: string;
  name: string;
}

// --- Face ---
export interface FaceRecognitionResponse {
  num_faces: number;
  recognized: boolean;
  student: StudentPublic | null;
  detected_student_ids: number[];
  message: string;
}

export interface RetrainResponse {
  success: boolean;
  message: string;
}

// --- Voice ---
export interface VoiceVerificationResponse {
  verified: boolean;
  student_id: number | null;
  student_name: string | null;
  score: number;
  threshold: number;
}

// --- Attendance ---
export interface AttendanceResultRow {
  name: string;
  student_id: number;
  source: string;
  status: string;
  is_present: boolean;
}

export interface AttendanceLogEntry {
  student_id: number;
  subject_id: number;
  timestamp: string;
  is_present: boolean;
}

export interface FaceAttendanceAnalyzeResponse {
  results: AttendanceResultRow[];
  logs: AttendanceLogEntry[];
  detected_ids: Record<string, string[]>;
  batch_id: string;
  photos_received: number;
  message: string | null;
}

export interface FaceAttendanceSummaryResponse {
  results: AttendanceResultRow[];
  logs: AttendanceLogEntry[];
  detected_ids: Record<string, string[]>;
  batch_id: string;
  photos_merged: number;
  message: string | null;
}

export interface VoiceAttendanceAnalyzeResponse {
  results: AttendanceResultRow[];
  logs: AttendanceLogEntry[];
  detected_scores: Record<string, number>;
  message: string | null;
}

export interface MarkAttendanceResponse {
  success: boolean;
  saved_count: number;
  message: string;
}

/** Shape of the 400 detail returned by /api/attendance/mark on bad entries. */
export interface MarkInvalidDetail {
  message: string;
  invalid_entries: { student_id: number; subject_id: number }[];
}

export interface AttendanceSummaryRow {
  ts_group: string | null;
  time: string;
  subject: string | null;
  subject_code: string | null;
  present_count: number;
  total_count: number;
  attendance_stats: string;
}

export interface TeacherAttendanceRecordsResponse {
  records: Record<string, unknown>[];
  summary: AttendanceSummaryRow[];
}

export interface StudentAttendanceResponse {
  logs: Record<string, unknown>[];
}

// --- Students ---
export interface StudentListResponse {
  students: StudentPublic[];
}

export interface StudentRegisterResponse {
  student: StudentPublic;
  classifier_trained: boolean;
  voice_enrolled: boolean;
  access_token: string;
  token_type: string;
  message: string;
}

export interface StudentLoginResponse {
  student: StudentPublic;
  access_token: string;
  token_type: string;
  message: string;
}

export interface EnrollResponse {
  success: boolean;
  already_enrolled: boolean;
  subject: SubjectPublic;
  message: string;
}

export interface UnenrollResponse {
  success: boolean;
  message: string;
}

export interface StudentSubjectStats {
  subject: SubjectPublic;
  total: number;
  attended: number;
}

export interface StudentSubjectsResponse {
  subjects: StudentSubjectStats[];
}

// --- Teachers ---
export interface TeacherRegisterResponse {
  success: boolean;
  message: string;
}

export interface TeacherLoginResponse {
  teacher: TeacherPublic;
  access_token: string;
  token_type: string;
}

export interface TeacherSubject extends SubjectPublic {
  total_students: number;
  total_classes: number;
}

export interface TeacherSubjectsResponse {
  subjects: TeacherSubject[];
}

// --- Subjects ---
export interface SubjectCreateResponse {
  subject: SubjectPublic;
}

export interface SubjectLookupResponse {
  subject: SubjectPublic;
}
