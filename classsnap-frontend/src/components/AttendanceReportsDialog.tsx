"use client";

/** "Attendance Reports" dialog (mirrors Streamlit attendance_result_dialog). */
import { Dialog, DialogContent, DialogHeader } from "@/components/ui/dialog";
import { AttendanceReview } from "@/components/AttendanceReview";
import type { AttendanceLogEntry, AttendanceResultRow } from "@/lib/types";

export function AttendanceReportsDialog({
  open,
  onOpenChange,
  results,
  logs,
  onSaved,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  results: AttendanceResultRow[];
  logs: AttendanceLogEntry[];
  onSaved: (savedCount: number) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader title="Attendance Reports" />
        <AttendanceReview
          results={results}
          logs={logs}
          onDiscard={() => onOpenChange(false)}
          onSaved={onSaved}
        />
      </DialogContent>
    </Dialog>
  );
}
