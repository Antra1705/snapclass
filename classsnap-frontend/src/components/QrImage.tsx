"use client";

/**
 * Renders the backend-generated QR PNG for a subject join link. The QR
 * endpoint requires teacher auth, so we fetch it as an authenticated blob and
 * render an object URL (a plain <img src> can't send the bearer token).
 */
import { useEffect, useState } from "react";
import { subjectQrBlob } from "@/lib/endpoints";
import { Alert, Spinner } from "@/components/ui/feedback";
import { detailToMessage, ApiError } from "@/lib/api";

export function QrImage({ subjectCode }: { subjectCode: string }) {
  const [url, setUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;
    const baseUrl = typeof window !== "undefined" ? window.location.origin : "http://localhost:3000";

    subjectQrBlob(subjectCode, baseUrl)
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setUrl(objectUrl);
      })
      .catch((e) => {
        if (cancelled) return;
        setError(e instanceof ApiError ? e.message : detailToMessage(null, "Could not load QR code"));
      });

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [subjectCode]);

  if (error) return <Alert variant="warning">{error}</Alert>;
  if (!url) return <Spinner label="Generating QR…" />;
  // eslint-disable-next-line @next/next/no-img-element
  return <img src={url} alt="Class join QR code" className="h-44 w-44 rounded-lg border border-slate-200" />;
}
