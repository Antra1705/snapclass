"use client";

/**
 * Review table shown before persisting attendance (mirrors the Streamlit
 * attendance results dialog: Name / ID / Source / Status columns, Discard +
 * Confirm & Save). The structured 400 from /api/attendance/mark (unenrolled
 * students) is surfaced by ErrorNotice.
 */
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Alert, ErrorNotice } from "@/components/ui/feedback";
import { markAttendance } from "@/lib/endpoints";
import type { AttendanceLogEntry, AttendanceResultRow } from "@/lib/types";

export function AttendanceReview({
  results,
  logs,
  onSaved,
  onDiscard,
}: {
  results: AttendanceResultRow[];
  logs: AttendanceLogEntry[];
  onSaved: (savedCount: number) => void;
  onDiscard: () => void;
}) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      const res = await markAttendance(logs);
      onSaved(res.saved_count);
    } catch (e) {
      setError(e);
    } finally {
      setSaving(false);
    }
  };

  if (results.length === 0) {
    return (
      <div className="space-y-4">
        <Alert variant="warning">No students enrolled in this course</Alert>
        <Button variant="secondary" onClick={onDiscard}>
          Close
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-600">Please review attendance before confirming.</p>

      <div className="max-h-72 overflow-y-auto rounded-[12px] border border-slate-300 bg-white">
        <table className="w-full text-left text-sm">
          <thead className="sticky top-0 bg-lavender text-ink">
            <tr>
              <th className="px-3 py-2 font-semibold">Name</th>
              <th className="px-3 py-2 font-semibold">ID</th>
              <th className="px-3 py-2 font-semibold">Source</th>
              <th className="px-3 py-2 font-semibold">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {results.map((r) => (
              <tr key={r.student_id}>
                <td className="px-3 py-2 text-ink">{r.name}</td>
                <td className="px-3 py-2 text-slate-500">{r.student_id}</td>
                <td className="px-3 py-2 text-slate-500">{r.source}</td>
                <td className="px-3 py-2">{r.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {error ? <ErrorNotice error={error} /> : null}

      <div className="flex gap-3">
        <Button variant="secondary" onClick={onDiscard} disabled={saving} className="flex-1">
          Discard
        </Button>
        <Button onClick={save} loading={saving} className="flex-1">
          Confirm &amp; Save
        </Button>
      </div>
    </div>
  );
}
