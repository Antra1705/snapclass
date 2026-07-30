"use client";

/**
 * Single-frame face capture. Uses getUserMedia + a canvas snapshot (NOT
 * continuous video streaming) with a file-input fallback (capture="user").
 * Discrete UX: start camera -> capture one frame -> preview -> retake/confirm.
 * Emits the captured frame as a JPEG Blob via onChange.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/feedback";

export function CameraCapture({
  onChange,
}: {
  onChange: (blob: Blob | null, previewUrl: string | null) => void;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [preview, setPreview] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const stopStream = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    setStreaming(false);
  }, []);

  useEffect(() => stopStream, [stopStream]);

  const startCamera = useCallback(async () => {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user" },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setStreaming(true);
    } catch {
      setError(
        "Could not access the camera. Grant permission, or use “Upload a photo instead”."
      );
    }
  }, []);

  const capture = useCallback(() => {
    const video = videoRef.current;
    if (!video) return;
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    canvas.toBlob(
      (blob) => {
        if (!blob) return;
        const url = URL.createObjectURL(blob);
        setPreview(url);
        onChange(blob, url);
        stopStream();
      },
      "image/jpeg",
      0.92
    );
  }, [onChange, stopStream]);

  const retake = useCallback(() => {
    if (preview) URL.revokeObjectURL(preview);
    setPreview(null);
    onChange(null, null);
    void startCamera();
  }, [preview, onChange, startCamera]);

  const onFile = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;
      if (preview) URL.revokeObjectURL(preview);
      const url = URL.createObjectURL(file);
      setPreview(url);
      onChange(file, url);
    },
    [onChange, preview]
  );

  return (
    <div className="space-y-3">
      <div className="overflow-hidden rounded-xl border border-slate-200 bg-slate-900/5">
        {preview ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={preview} alt="Captured face" className="max-h-72 w-full object-contain" />
        ) : (
          <video
            ref={videoRef}
            playsInline
            muted
            className="max-h-72 w-full bg-black object-contain"
          />
        )}
      </div>

      {error ? <Alert variant="warning">{error}</Alert> : null}

      <div className="flex flex-wrap gap-2">
        {!preview && !streaming ? (
          <Button type="button" onClick={startCamera}>
            Start camera
          </Button>
        ) : null}
        {!preview && streaming ? (
          <Button type="button" onClick={capture}>
            Capture photo
          </Button>
        ) : null}
        {preview ? (
          <Button type="button" variant="outline" onClick={retake}>
            Retake
          </Button>
        ) : null}

        <label className="inline-flex h-10 cursor-pointer items-center rounded-lg border border-slate-300 bg-white px-4 text-sm font-medium text-slate-800 hover:bg-slate-50">
          Upload a photo instead
          <input
            type="file"
            accept="image/*"
            capture="user"
            className="hidden"
            onChange={onFile}
          />
        </label>
      </div>
    </div>
  );
}
