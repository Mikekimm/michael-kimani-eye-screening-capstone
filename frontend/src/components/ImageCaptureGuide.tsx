import { Camera, ImageUp } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";

import { analyseImage, type QualityHints } from "@/lib/imageQuality";

import { Button } from "./ui/primitives";

const ACCEPTED = ["image/jpeg", "image/png"];

/**
 * Camera capture with a circular framing guide, plus a gallery fallback. On phones the camera
 * input opens the rear camera; browsers without camera support fall back to a file picker.
 * Once a photo is chosen only its preview is shown (the screen offers Cancel / Analyse). After the
 * server refused a photo, ``rejection`` explains why and the buttons read "Retake" / "Upload another".
 */
export function ImageCaptureGuide({ onImage, rejection }: { onImage: (file: File | null) => void; rejection?: string | null }) {
  const cameraId = useId();
  const galleryId = useId();
  const cameraRef = useRef<HTMLInputElement>(null);
  const galleryRef = useRef<HTMLInputElement>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [hints, setHints] = useState<QualityHints | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);

  const handle = async (file: File | undefined) => {
    setError(null);
    setHints(null);
    if (!file) return;
    if (!ACCEPTED.includes(file.type)) {
      setError("Please use a JPEG or PNG photo. If your phone saves HEIC photos, change the camera format to 'Most compatible'.");
      onImage(null);
      return;
    }
    setPreview(URL.createObjectURL(file));
    onImage(file);
    try {
      setHints(await analyseImage(file));
    } catch {
      setHints(null); // hints are optional; the server still checks quality
    }
  };

  return (
    <div className="flex flex-col gap-3">
      <div className="relative mx-auto aspect-square w-full max-w-xs overflow-hidden rounded-full bg-foreground/90 ring-4 ring-primary/30">
        {preview ? (
          <img src={preview} alt="Captured fundus photo preview" className="h-full w-full object-cover" />
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-2 p-8 text-center text-sm text-white/80">
            <Camera aria-hidden className="h-8 w-8" />
            Centre the optic disc and retina inside this circle. Keep the lens steady and avoid glare.
          </div>
        )}
        <div aria-hidden className="pointer-events-none absolute inset-6 rounded-full border-2 border-dashed border-white/60" />
      </div>

      {rejection && !preview && (
        <div role="alert" data-testid="photo-rejected" className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">
          <p>{rejection}</p>
          <p className="mt-1 text-foreground">Nothing was saved. Retake the photo or upload another one.</p>
        </div>
      )}

      <div className={preview ? "hidden" : "grid grid-cols-2 gap-2"}>
        <input ref={cameraRef} id={cameraId} type="file" accept="image/*" capture="environment" className="sr-only"
          aria-label="Take a fundus photo with the camera" tabIndex={-1}
          onChange={(e) => void handle(e.target.files?.[0])} />
        <Button type="button" onClick={() => cameraRef.current?.click()}><Camera aria-hidden className="h-4 w-4" />{rejection ? "Retake" : "Take photo"}</Button>
        <input ref={galleryRef} id={galleryId} type="file" accept="image/jpeg,image/png" className="sr-only"
          aria-label="Choose a fundus photo from the gallery" tabIndex={-1}
          onChange={(e) => void handle(e.target.files?.[0])} />
        <Button type="button" variant="outline" onClick={() => galleryRef.current?.click()}><ImageUp aria-hidden className="h-4 w-4" />{rejection ? "Upload another" : "From gallery"}</Button>
      </div>
      <p className={preview ? "hidden" : "text-xs text-muted-foreground"}>
        If the camera does not open, check that this site is allowed to use the camera, or choose a photo from the gallery.
      </p>

      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      {hints && (
        <div role="status" className="rounded-md border p-3 text-sm">
          {hints.hints.length === 0 ? (
            <p className="text-risk-low">Photo looks usable ({hints.width}x{hints.height}). The server will check it again.</p>
          ) : (
            <ul className="list-disc space-y-1 pl-5 text-risk-medium">{hints.hints.map((h) => <li key={h}>{h}</li>)}</ul>
          )}
        </div>
      )}
    </div>
  );
}
