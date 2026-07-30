"use client";

/**
 * "Capture or upload photos" dialog (mirrors the Streamlit add_photos_dialog):
 * Camera / Upload toggle, adds photos to the page gallery, Done closes.
 * Analysis happens later from the page via "Run Face Analysis".
 */
import { useCallback, useState } from "react";
import { Dialog, DialogContent, DialogHeader } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { CameraCapture } from "@/components/CameraCapture";

export interface GalleryPhoto {
  id: number;
  blob: Blob;
  previewUrl: string;
}

export function AddPhotosDialog({
  open,
  onOpenChange,
  onAdd,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onAdd: (blob: Blob, previewUrl: string) => void;
}) {
  const [tab, setTab] = useState<"camera" | "upload">("camera");
  // Discrete UX: captured frame is held as "pending" until the user
  // explicitly adds it; the capture component is remounted after each add.
  const [pending, setPending] = useState<{ blob: Blob; url: string } | null>(null);
  const [camKey, setCamKey] = useState(0);

  const onCameraChange = useCallback((blob: Blob | null, previewUrl: string | null) => {
    setPending(blob && previewUrl ? { blob, url: previewUrl } : null);
  }, []);

  const addPending = useCallback(() => {
    if (!pending) return;
    onAdd(pending.blob, pending.url);
    setPending(null);
    setCamKey((k) => k + 1);
  }, [pending, onAdd]);

  const onFiles = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = Array.from(e.target.files ?? []);
      e.target.value = "";
      for (const file of files) onAdd(file, URL.createObjectURL(file));
    },
    [onAdd]
  );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader
          title="Capture or upload photos"
          description="Add classroom photos to scan for attendance"
        />

        <div className="mb-4 flex gap-3">
          <Button
            variant={tab === "camera" ? "primary" : "tertiary"}
            className="flex-1"
            onClick={() => setTab("camera")}
          >
            Camera
          </Button>
          <Button
            variant={tab === "upload" ? "primary" : "tertiary"}
            className="flex-1"
            onClick={() => setTab("upload")}
          >
            Upload photos
          </Button>
        </div>

        {tab === "camera" ? (
          <div className="space-y-3">
            <CameraCapture key={camKey} onChange={onCameraChange} />
            {pending ? (
              <Button variant="secondary" className="w-full" onClick={addPending}>
                Add this photo
              </Button>
            ) : null}
          </div>
        ) : (
          <label className="flex h-32 cursor-pointer flex-col items-center justify-center gap-1 rounded-[20px] border border-dashed border-slate-400 bg-white text-sm text-slate-500 hover:bg-slate-50">
            <span className="font-semibold text-ink">Choose image files</span>
            <span>JPG / PNG — you can select several at once</span>
            <input type="file" accept="image/*" multiple className="hidden" onChange={onFiles} />
          </label>
        )}

        <hr className="my-5 border-slate-300" />

        <Button className="w-full" onClick={() => onOpenChange(false)}>
          Done
        </Button>
      </DialogContent>
    </Dialog>
  );
}
