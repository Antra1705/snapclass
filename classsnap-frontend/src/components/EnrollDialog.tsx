"use client";

/**
 * Student enroll-by-code dialog (mirrors Streamlit enroll/auto-enroll). Handles
 * not-found (404), already-enrolled (200 with already_enrolled), and rate
 * limiting (429) explicitly.
 */
import { useCallback, useEffect, useState } from "react";
import { Dialog, DialogContent, DialogHeader } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/input";
import { Alert, ErrorNotice } from "@/components/ui/feedback";
import { studentEnroll } from "@/lib/endpoints";

export function EnrollDialog({
  open,
  onOpenChange,
  studentId,
  initialCode,
  onEnrolled,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  studentId: number;
  initialCode?: string;
  onEnrolled: () => void;
}) {
  const [code, setCode] = useState(initialCode ?? "");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [notice, setNotice] = useState<{ variant: "success" | "warning"; text: string } | null>(
    null
  );

  useEffect(() => {
    if (open) setCode(initialCode ?? "");
  }, [open, initialCode]);

  const reset = useCallback(() => {
    setError(null);
    setNotice(null);
    setSubmitting(false);
  }, []);

  const handleOpenChange = (next: boolean) => {
    if (!next) reset();
    onOpenChange(next);
  };

  const submit = async () => {
    if (!code.trim()) {
      setError(new Error("Please enter a subject code."));
      return;
    }
    setSubmitting(true);
    setError(null);
    setNotice(null);
    try {
      const res = await studentEnroll(studentId, code.trim());
      if (res.already_enrolled) {
        setNotice({ variant: "warning", text: res.message });
      } else {
        setNotice({ variant: "success", text: `${res.message} (${res.subject.name})` });
        onEnrolled();
      }
    } catch (e) {
      setError(e);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent>
        <DialogHeader
          title="Enroll in Subject"
          description="Enter the subject code provided by your teacher to enroll"
        />
        <div className="space-y-1">
          <Field label="Subject Code">
            <Input
              value={code}
              onChange={(e) => setCode(e.target.value.toUpperCase())}
              placeholder="Eg. CS101"
              autoFocus
            />
          </Field>
          {error ? <ErrorNotice error={error} /> : null}
          {notice ? <Alert variant={notice.variant}>{notice.text}</Alert> : null}
          <Button className="mt-3 w-full" onClick={submit} loading={submitting}>
            Enroll now
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
