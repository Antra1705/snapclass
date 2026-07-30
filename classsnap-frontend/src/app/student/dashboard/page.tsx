"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { Button } from "@/components/ui/button";
import { Alert, ErrorNotice, Spinner } from "@/components/ui/feedback";
import { useAuth, useRequireRole } from "@/lib/auth";
import { useAsync } from "@/lib/useAsync";
import { useQueryParam } from "@/lib/useQueryParam";
import { studentAttendance, studentSubjects, studentUnenroll } from "@/lib/endpoints";
import { EnrollDialog } from "@/components/EnrollDialog";
import { SubjectCard } from "@/components/SubjectCard";

export default function StudentDashboardPage() {
  const { ready } = useRequireRole("student");
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

interface AttendanceLog {
  subject_id?: number;
  timestamp?: string;
  is_present?: boolean;
  subjects?: { name?: string; subject_code?: string } | null;
}

function DashboardBody() {
  const { auth } = useAuth();
  const studentId = auth!.id;
  const joinCode = useQueryParam("join-code");
  const [enrollOpen, setEnrollOpen] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const subjectsQuery = useAsync(() => studentSubjects(studentId), [studentId]);
  const attendanceQuery = useAsync(() => studentAttendance(studentId), [studentId]);

  // Auto-open the enroll dialog when arriving via a QR/join-code link.
  useEffect(() => {
    if (joinCode) setEnrollOpen(true);
  }, [joinCode]);

  const reloadAll = () => {
    subjectsQuery.reload();
    attendanceQuery.reload();
  };

  const unenroll = async (subjectId: number, name: string) => {
    try {
      await studentUnenroll(studentId, subjectId);
      setToast(`Unenrolled from ${name} successfully!`);
      reloadAll();
    } catch {
      setToast(null);
      alert("Could not unenroll. Please try again.");
    }
  };

  const logs = (attendanceQuery.data?.logs as AttendanceLog[] | undefined) ?? [];

  return (
    <div className="space-y-8">
      {toast ? <Alert variant="success">{toast}</Alert> : null}

      <div className="flex items-center justify-between gap-4">
        <h2 className="font-display text-3xl text-ink">Your Enrolled Subjects</h2>
        <Button onClick={() => setEnrollOpen(true)}>Enroll in Subject</Button>
      </div>

      <hr className="border-slate-400/50" />

      <section>
        {subjectsQuery.loading ? (
          <Spinner label="Loading your enrolled subjects..." />
        ) : subjectsQuery.error ? (
          <ErrorNotice error={subjectsQuery.error} />
        ) : (subjectsQuery.data?.subjects.length ?? 0) === 0 ? (
          <Alert variant="info">You&apos;re not enrolled in any subjects yet.</Alert>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2">
            {subjectsQuery.data!.subjects.map(({ subject, total, attended }) => (
              <SubjectCard
                key={subject.subject_id}
                name={subject.name}
                code={subject.subject_code}
                section={subject.section}
                stats={[
                  { icon: "📅", label: "Total", value: total },
                  { icon: "✅", label: "Attended", value: attended },
                ]}
                footer={
                  <Button
                    variant="tertiary"
                    size="sm"
                    className="w-full"
                    onClick={() => unenroll(subject.subject_id, subject.name)}
                  >
                    Unenroll from this course
                  </Button>
                }
              />
            ))}
          </div>
        )}
      </section>

      <section>
        <h3 className="mb-4 font-display text-2xl text-ink">Attendance history</h3>
        {attendanceQuery.loading ? (
          <Spinner label="Loading history…" />
        ) : attendanceQuery.error ? (
          <ErrorNotice error={attendanceQuery.error} />
        ) : logs.length === 0 ? (
          <Alert variant="info">No attendance records yet.</Alert>
        ) : (
          <div className="overflow-x-auto rounded-[12px] border border-slate-300 bg-white">
            <table className="w-full text-left text-sm">
              <thead className="bg-lavender text-ink">
                <tr>
                  <th className="px-4 py-2 font-semibold">When</th>
                  <th className="px-4 py-2 font-semibold">Subject</th>
                  <th className="px-4 py-2 font-semibold">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {logs.map((log, i) => (
                  <tr key={i}>
                    <td className="px-4 py-2 text-slate-600">{log.timestamp ?? "—"}</td>
                    <td className="px-4 py-2 text-ink">{log.subjects?.name ?? "—"}</td>
                    <td className="px-4 py-2">{log.is_present ? "✅ Present" : "❌ Absent"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <EnrollDialog
        open={enrollOpen}
        onOpenChange={setEnrollOpen}
        studentId={studentId}
        initialCode={joinCode ?? undefined}
        onEnrolled={reloadAll}
      />
    </div>
  );
}
