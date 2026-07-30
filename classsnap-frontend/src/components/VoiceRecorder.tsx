"use client";

/**
 * Fixed-clip voice capture via the MediaRecorder API (NOT streaming). Record ->
 * stop on user action -> preview -> re-record. Emits a WAV Blob (transcoded
 * from the recording) via onChange so the backend's librosa.load can read it.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Alert, Spinner } from "@/components/ui/feedback";
import { blobToWav } from "@/lib/wav";

export function VoiceRecorder({ onChange }: { onChange: (wav: Blob | null) => void }) {
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const [recording, setRecording] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [encoding, setEncoding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const cleanupStream = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = null;
  }, []);

  useEffect(() => cleanupStream, [cleanupStream]);

  const start = useCallback(async () => {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      chunksRef.current = [];
      const recorder = new MediaRecorder(stream);
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = async () => {
        cleanupStream();
        const raw = new Blob(chunksRef.current, { type: chunksRef.current[0]?.type || "audio/webm" });
        setEncoding(true);
        try {
          const wav = await blobToWav(raw);
          const url = URL.createObjectURL(wav);
          setPreviewUrl(url);
          onChange(wav);
        } catch {
          setError("Could not process the recording. Please try again.");
          onChange(null);
        } finally {
          setEncoding(false);
        }
      };
      recorder.start();
      recorderRef.current = recorder;
      setRecording(true);
      setElapsed(0);
      timerRef.current = setInterval(() => setElapsed((s) => s + 1), 1000);
    } catch {
      setError("Could not access the microphone. Please grant permission and retry.");
    }
  }, [cleanupStream, onChange]);

  const stop = useCallback(() => {
    recorderRef.current?.stop();
    recorderRef.current = null;
    setRecording(false);
  }, []);

  const reset = useCallback(() => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(null);
    onChange(null);
  }, [previewUrl, onChange]);

  return (
    <div className="space-y-3">
      {error ? <Alert variant="warning">{error}</Alert> : null}

      {previewUrl ? (
        <audio controls src={previewUrl} className="w-full" />
      ) : (
        <div className="flex h-12 items-center rounded-lg border border-dashed border-slate-300 px-3 text-sm text-slate-500">
          {recording ? `Recording… ${elapsed}s` : encoding ? <Spinner label="Processing…" /> : "No clip recorded yet"}
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        {!recording && !previewUrl ? (
          <Button type="button" onClick={start} loading={encoding}>
            Start recording
          </Button>
        ) : null}
        {recording ? (
          <Button type="button" variant="secondary" onClick={stop}>
            Stop
          </Button>
        ) : null}
        {previewUrl ? (
          <Button type="button" variant="outline" onClick={reset}>
            Re-record
          </Button>
        ) : null}
      </div>
    </div>
  );
}
