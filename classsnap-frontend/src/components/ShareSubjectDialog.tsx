"use client";

/** "Share Class Link" dialog (mirrors Streamlit share_subject_dialog). */
import { Dialog, DialogContent, DialogHeader } from "@/components/ui/dialog";
import { Alert } from "@/components/ui/feedback";
import { QrImage } from "@/components/QrImage";

export function ShareSubjectDialog({
  open,
  onOpenChange,
  subjectName,
  subjectCode,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  subjectName: string;
  subjectCode: string;
}) {
  const joinUrl =
    typeof window !== "undefined" ? `${window.location.origin}/?join-code=${subjectCode}` : "";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="w-[min(92vw,640px)]">
        <DialogHeader title="Share Class Link" description={subjectName} />

        <h3 className="mb-4 font-display text-2xl text-ink">Scan to Join</h3>

        <div className="grid gap-6 sm:grid-cols-2">
          <div>
            <h4 className="mb-2 font-semibold text-ink">Copy Link</h4>
            <code className="mb-2 block break-all rounded-md bg-slate-100 px-3 py-2 text-xs text-ink">
              {joinUrl}
            </code>
            <code className="mb-3 block w-fit rounded-md bg-slate-100 px-3 py-2 text-sm font-semibold tracking-widest text-ink">
              {subjectCode}
            </code>
            <Alert variant="info">Copy this link to share on Whatsapp or Email</Alert>
          </div>

          <div className="flex flex-col items-center gap-1">
            <h4 className="mb-1 self-start font-semibold text-ink">Scan to Join</h4>
            <QrImage subjectCode={subjectCode} />
            <p className="text-xs text-slate-500">QRCODE for class joining</p>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
