"use client";

/**
 * Teacher voice-attendance session (mirrors Streamlit voice_attendance_dialog).
 * Record one classroom clip -> /api/attendance/analyze-voice (multi-speaker
 * bulk match) -> review -> /api/attendance/mark. This uses analyze-voice, not
 * /api/voice/verify, because verify identifies a single speaker and cannot
 * mark a whole roster.
 */
import { useCallback, useState } from "react";
import { Dialog, DialogContent, DialogHeader } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { ErrorNotice } from "@/components/ui/feedback";
import { VoiceRecorder } from "@/components/VoiceRecorder";
import { AttendanceReview } from "@/components/AttendanceReview";
import { analyzeVoice } from "@/lib/endpoints";
import type { AttendanceLogEntry, AttendanceResultRow } from "@/lib/types";

export function VoiceAttendanceDialog({
  open,
  onOpenChange,
  subjectId,
  subjectLabel,
  onSaved,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  subjectId: number;
  subjectLabel: string;
  onSaved: (savedCount: number) => void;
}) {
  const [clip, setClip] = useState<Blob | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [review, setReview] = useState<{
    results: AttendanceResultRow[];
    logs: AttendanceLogEntry[];
  } | null>(null);

  const reset = useCallback(() => {
    setClip(null);
    setReview(null);
    setError(null);
    setAnalyzing(false);
  }, []);

  const handleOpenChange = (next: boolean) => {
    if (!next) reset();
    onOpenChange(next);
  };

  const analyze = async () => {
    if (!clip) return;
    setAnalyzing(true);
    setError(null);
    try {
      const res = await analyzeVoice({ file: clip, subjectId });
      setReview({ results: res.results, logs: res.logs });
    } catch (e) {
      setError(e);
    } finally {
      setAnalyzing(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent>
        <DialogHeader
          title="Voice Attendance"
          description={
            review
              ? subjectLabel
              : "Record audio of students saying I am present. The AI will recognize the students."
          }
        />

        {review ? (
          <AttendanceReview
            results={review.results}
            logs={review.logs}
            onDiscard={() => handleOpenChange(false)}
            onSaved={(count) => {
              onSaved(count);
              handleOpenChange(false);
            }}
          />
        ) : (
          <div className="space-y-4">
            <p className="text-sm font-medium text-ink">Record classroom audio</p>
            <VoiceRecorder onChange={setClip} />
            {error ? <ErrorNotice error={error} /> : null}
            <Button onClick={analyze} loading={analyzing} disabled={!clip} className="w-full">
              Analyze Audio
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
