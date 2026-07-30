"use client";

import { useState } from "react";
import { AppShell } from "@/components/AppShell";
import { Button } from "@/components/ui/button";
import { Alert, ErrorNotice, Spinner } from "@/components/ui/feedback";
import { useAuth, useRequireRole } from "@/lib/auth";
import { useAsync } from "@/lib/useAsync";
import { analyzeFace, faceSummary, teacherAttendanceRecords, teacherSubjects } from "@/lib/endpoints";
import type { AttendanceLogEntry, AttendanceResultRow, TeacherSubject } from "@/lib/types";
import { AddPhotosDialog, type GalleryPhoto } from "@/components/AddPhotosDialog";
import { AttendanceReportsDialog } from "@/components/AttendanceReportsDialog";
import { VoiceAttendanceDialog } from "@/components/VoiceAttendanceDialog";
import { CreateSubjectDialog } from "@/components/CreateSubjectDialog";
import { ShareSubjectDialog } from "@/components/ShareSubjectDialog";
import { SubjectCard } from "@/components/SubjectCard";

type Tab = "take_attendance" | "manage_subjects" | "attendance_records";

export default function TeacherDashboardPage() {
  const { ready } = useRequireRole("teacher");
  if (!ready) {
    return (
      <AppShell>
        <Spinner label="Loading…" />
      </AppShell>
    );
  }
  return (
    <AppShell>
      <DashboardBody />
    </AppShell>
  );
}

function DashboardBody() {
  const { auth } = useAuth();
  const teacherId = auth!.id;
  const [tab, setTab] = useState<Tab>("take_attendance");
  const [toast, setToast] = useState<string | null>(null);

  const subjectsQuery = useAsync(() => teacherSubjects(teacherId), [teacherId]);

  const tabs: { key: Tab; label: string }[] = [
    { key: "take_attendance", label: "Take Attendance" },
    { key: "manage_subjects", label: "Manage Subjects" },
    { key: "attendance_records", label: "Attendance Records" },
  ];

  return (
    <div>
      {toast ? (
        <Alert variant="success" className="mb-4">
          {toast}
        </Alert>
      ) : null}

      {/* Tab buttons: active = blurple, inactive = black (as in the original). */}
      <div className="grid grid-cols-3 gap-3">
        {tabs.map((t) => (
          <Button
            key={t.key}
            variant={tab === t.key ? "primary" : "tertiary"}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </Button>
        ))}
      </div>

      <hr className="my-6 border-slate-400/50" />

      {subjectsQuery.loading ? (
        <Spinner label="Loading subjects…" />
      ) : subjectsQuery.error ? (
        <ErrorNotice error={subjectsQuery.error} />
      ) : tab === "take_attendance" ? (
        <TakeAttendanceTab
          subjects={subjectsQuery.data?.subjects ?? []}
          onSaved={() => setToast("Attendance taken")}
        />
      ) : tab === "manage_subjects" ? (
        <ManageSubjectsTab
          subjects={subjectsQuery.data?.subjects ?? []}
          onChanged={() => subjectsQuery.reload()}
        />
      ) : (
        <AttendanceRecordsTab teacherId={teacherId} />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Take Attendance (mirrors teacher_tab_take_attendance)
// ---------------------------------------------------------------------------

function TakeAttendanceTab({
  subjects,
  onSaved,
}: {
  subjects: TeacherSubject[];
  onSaved: () => void;
}) {
  const [selectedId, setSelectedId] = useState<number | null>(subjects[0]?.subject_id ?? null);
  const [photos, setPhotos] = useState<GalleryPhoto[]>([]);
  const [addOpen, setAddOpen] = useState(false);
  const [voiceOpen, setVoiceOpen] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisError, setAnalysisError] = useState<unknown>(null);
  const [report, setReport] = useState<{
    results: AttendanceResultRow[];
    logs: AttendanceLogEntry[];
  } | null>(null);

  const selected = subjects.find((s) => s.subject_id === selectedId) ?? null;

  if (subjects.length === 0) {
    return (
      <Alert variant="warning">
        You have not created any subjects yet! Please create one to begin!
      </Alert>
    );
  }

  const addPhoto = (blob: Blob, previewUrl: string) =>
    setPhotos((prev) => [...prev, { id: Date.now() + prev.length, blob, previewUrl }]);

  const clearPhotos = () => {
    photos.forEach((p) => URL.revokeObjectURL(p.previewUrl));
    setPhotos([]);
  };

  // Upload each gallery photo into a fresh server batch, then merge via
  // face-summary (server rejects the merge if any upload was dropped).
  const runFaceAnalysis = async () => {
    if (!selected) return;
    setAnalyzing(true);
    setAnalysisError(null);
    try {
      let batchId: string | undefined;
      for (let i = 0; i < photos.length; i++) {
        const res = await analyzeFace({
          file: photos[i].blob,
          subjectId: selected.subject_id,
          photoLabel: `Photo ${i + 1}`,
          batchId,
        });
        batchId = res.batch_id;
      }
      const summary = await faceSummary({
        subject_id: selected.subject_id,
        batch_id: batchId!,
        expected_photos: photos.length,
      });
      setReport({ results: summary.results, logs: summary.logs });
    } catch (e) {
      setAnalysisError(e);
    } finally {
      setAnalyzing(false);
    }
  };

  const hasPhotos = photos.length > 0;

  return (
    <div>
      <h2 className="mb-6 font-display text-3xl text-ink">Take AI Attendance</h2>

      <div className="flex items-end gap-3">
        <div className="flex-[3]">
          <label className="mb-1 block text-sm font-medium text-ink">Select Subject</label>
          <select
            className="h-11 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm"
            value={selectedId ?? ""}
            onChange={(e) => setSelectedId(Number(e.target.value))}
          >
            {subjects.map((s) => (
              <option key={s.subject_id} value={s.subject_id}>
                {s.name} - {s.subject_code}
              </option>
            ))}
          </select>
        </div>
        <Button className="flex-1" onClick={() => setAddOpen(true)}>
          Add Photos
        </Button>
      </div>

      <hr className="my-6 border-slate-400/50" />

      {hasPhotos ? (
        <>
          <h3 className="mb-4 font-display text-2xl text-ink">Added Photos</h3>
          <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
            {photos.map((p, idx) => (
              <figure key={p.id}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={p.previewUrl}
                  alt={`Photo${idx + 1}`}
                  className="w-full rounded-[12px] border border-slate-300 object-cover"
                />
                <figcaption className="mt-1 text-center text-xs text-slate-500">
                  Photo{idx + 1}
                </figcaption>
              </figure>
            ))}
          </div>
        </>
      ) : null}

      {analysisError ? (
        <div className="mb-4">
          <ErrorNotice error={analysisError} />
        </div>
      ) : null}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <Button variant="tertiary" disabled={!hasPhotos || analyzing} onClick={clearPhotos}>
          Clear all photos
        </Button>
        <Button
          variant="secondary"
          disabled={!hasPhotos}
          loading={analyzing}
          onClick={runFaceAnalysis}
        >
          Run Face Analysis
        </Button>
        <Button variant="primary" disabled={!selected} onClick={() => setVoiceOpen(true)}>
          Use Voice Attendance
        </Button>
      </div>

      <AddPhotosDialog open={addOpen} onOpenChange={setAddOpen} onAdd={addPhoto} />

      {report ? (
        <AttendanceReportsDialog
          open={!!report}
          onOpenChange={(o) => !o && setReport(null)}
          results={report.results}
          logs={report.logs}
          onSaved={() => {
            setReport(null);
            clearPhotos();
            onSaved();
          }}
        />
      ) : null}

      {selected ? (
        <VoiceAttendanceDialog
          open={voiceOpen}
          onOpenChange={setVoiceOpen}
          subjectId={selected.subject_id}
          subjectLabel={`${selected.name} - ${selected.subject_code}`}
          onSaved={onSaved}
        />
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Manage Subjects (mirrors teacher_tab_manage_subjects)
// ---------------------------------------------------------------------------

function ManageSubjectsTab({
  subjects,
  onChanged,
}: {
  subjects: TeacherSubject[];
  onChanged: () => void;
}) {
  const [createOpen, setCreateOpen] = useState(false);
  const [share, setShare] = useState<TeacherSubject | null>(null);

  return (
    <div>
      <div className="mb-6 flex items-center justify-between gap-4">
        <h2 className="font-display text-3xl text-ink">Manage Subjects</h2>
        <Button variant="secondary" onClick={() => setCreateOpen(true)}>
          Create New Subject
        </Button>
      </div>

      {subjects.length === 0 ? (
        <Alert variant="info">NO SUBJECTS FOUND. CREATE ONE ABOVE</Alert>
      ) : (
        <div className="space-y-4">
          {subjects.map((s) => (
            <SubjectCard
              key={s.subject_id}
              name={s.name}
              code={s.subject_code}
              section={s.section}
              stats={[
                { icon: "🫂", label: "Students", value: s.total_students },
                { icon: "🕰️", label: "Classes", value: s.total_classes },
              ]}
              footer={
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setShare(s)}
                  disabled={!s.subject_code}
                >
                  Share Code: {s.name}
                </Button>
              }
            />
          ))}
        </div>
      )}

      <CreateSubjectDialog open={createOpen} onOpenChange={setCreateOpen} onCreated={onChanged} />
      {share && share.subject_code ? (
        <ShareSubjectDialog
          open={!!share}
          onOpenChange={(o) => !o && setShare(null)}
          subjectName={share.name}
          subjectCode={share.subject_code}
        />
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Attendance Records (mirrors teacher_tab_attendance_records)
// ---------------------------------------------------------------------------

function AttendanceRecordsTab({ teacherId }: { teacherId: number }) {
  const query = useAsync(() => teacherAttendanceRecords(teacherId), [teacherId]);

  if (query.loading) return <Spinner label="Loading records…" />;
  if (query.error) return <ErrorNotice error={query.error} />;

  const summary = query.data?.summary ?? [];

  return (
    <div>
      <h2 className="mb-6 font-display text-3xl text-ink">Attendance Records</h2>

      {summary.length === 0 ? (
        <Alert variant="info">No attendance has been recorded yet.</Alert>
      ) : (
        <div className="overflow-x-auto rounded-[12px] border border-slate-300 bg-white">
          <table className="w-full text-left text-sm">
            <thead className="bg-lavender text-ink">
              <tr>
                <th className="px-4 py-2 font-semibold">Time</th>
                <th className="px-4 py-2 font-semibold">Subject</th>
                <th className="px-4 py-2 font-semibold">Subject Code</th>
                <th className="px-4 py-2 font-semibold">Attendance Stats</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {summary.map((r, i) => (
                <tr key={`${r.ts_group}-${i}`}>
                  <td className="px-4 py-2 text-ink">{r.time}</td>
                  <td className="px-4 py-2 text-ink">{r.subject ?? "—"}</td>
                  <td className="px-4 py-2 text-slate-500">{r.subject_code ?? "—"}</td>
                  <td className="px-4 py-2 text-ink">{r.attendance_stats}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
