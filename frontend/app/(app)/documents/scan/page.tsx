"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Camera, Check, Plus, SwitchCamera, X } from "lucide-react";
import { toast } from "sonner";
import { api, apiForm } from "@/lib/api";
import { SCAN_MAX_PAGES, clampCrop, cropToJpeg, jpegsToPdf, type CropNorm } from "@/lib/scan-pdf";
import { PageCropper } from "@/components/page-cropper";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type Collection = {
  id: string;
  name: string;
  parent_id?: string | null;
  is_default?: boolean;
  shared?: boolean;
};

type Page = { preview: string; jpeg: Uint8Array; width: number; height: number };

const FULL_CROP: CropNorm = { x: 0, y: 0, w: 1, h: 1 };

function todayLabel() {
  return new Date().toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

export default function ScanPage() {
  const router = useRouter();
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const cropRef = useRef<CropNorm>(clampCrop({ x: 0.06, y: 0.06, w: 0.88, h: 0.88 }));
  const [step, setStep] = useState<"camera" | "crop" | "save">("camera");
  const [facing, setFacing] = useState<"environment" | "user">("environment");
  const [live, setLive] = useState(false);
  const [shot, setShot] = useState<string>("");
  const [shotBlob, setShotBlob] = useState<Blob | null>(null);
  const [pages, setPages] = useState<Page[]>([]);
  const [collections, setCollections] = useState<Collection[]>([]);
  const [targetId, setTargetId] = useState("");
  const [title, setTitle] = useState(`Scan ${todayLabel()}`);
  const [busy, setBusy] = useState(false);

  const onCrop = useCallback((next: CropNorm) => {
    cropRef.current = next;
  }, []);

  useEffect(() => {
    api<Collection[]>("/collections")
      .then((cols) => {
        const owned = cols.filter((col) => !col.shared);
        setCollections(owned);
        const fallback = owned.find((col) => col.is_default) || owned[0];
        setTargetId(fallback?.id || "");
      })
      .catch(() => undefined);
  }, []);

  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    setLive(false);
  }, []);

  const startCamera = useCallback(async () => {
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) return false;
    stopCamera();
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: { facingMode: { ideal: facing }, width: { ideal: 1920 }, height: { ideal: 1080 } },
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play().catch(() => undefined);
      }
      setLive(true);
      return true;
    } catch {
      setLive(false);
      return false;
    }
  }, [facing, stopCamera]);

  useEffect(() => {
    if (step !== "camera") {
      stopCamera();
      return;
    }
    void startCamera();
    return () => stopCamera();
  }, [step, startCamera, stopCamera]);

  useEffect(() => {
    return () => {
      stopCamera();
      if (shot) URL.revokeObjectURL(shot);
      pages.forEach((page) => URL.revokeObjectURL(page.preview));
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function close() {
    stopCamera();
    const last = typeof window !== "undefined" ? sessionStorage.getItem("dv_return") : null;
    if (last && !last.startsWith("/documents/scan")) router.push(last);
    else router.push("/home");
  }

  async function captureFrame() {
    const video = videoRef.current;
    if (!video || !live || video.videoWidth < 8) {
      fileRef.current?.click();
      return;
    }
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.drawImage(video, 0, 0);
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.92));
    if (!blob) {
      toast.error("Could not capture that page");
      return;
    }
    if (shot) URL.revokeObjectURL(shot);
    setShotBlob(blob);
    setShot(URL.createObjectURL(blob));
    setStep("crop");
  }

  function onPicked(file: File | undefined) {
    if (!file) return;
    if (shot) URL.revokeObjectURL(shot);
    setShotBlob(file);
    setShot(URL.createObjectURL(file));
    setStep("crop");
  }

  async function keepPage() {
    if (!shotBlob) return;
    if (pages.length >= SCAN_MAX_PAGES) {
      toast.error(`A scan can have at most ${SCAN_MAX_PAGES} pages`);
      return;
    }
    setBusy(true);
    try {
      const cropped = await cropToJpeg(shotBlob, cropRef.current);
      const jpeg = new Uint8Array(await cropped.blob.arrayBuffer());
      setPages((current) => [
        ...current,
        { preview: URL.createObjectURL(cropped.blob), jpeg, width: cropped.width, height: cropped.height },
      ]);
      if (shot) URL.revokeObjectURL(shot);
      setShot("");
      setShotBlob(null);
      setStep("camera");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not crop that page");
    } finally {
      setBusy(false);
    }
  }

  async function savePdf() {
    if (!pages.length) return;
    const name = title.trim() || `Scan ${todayLabel()}`;
    setBusy(true);
    try {
      const file = await jpegsToPdf(
        pages.map((page) => ({ jpeg: page.jpeg, width: page.width, height: page.height })),
        `${name}.pdf`,
      );
      const body = new FormData();
      body.append("files", file);
      body.append("title", name);
      if (targetId) body.append("collection_id", targetId);
      const result = await apiForm<{ documents: Array<{ id: string; duplicate?: boolean }> }>("/documents/upload", body);
      const doc = result.documents?.[0];
      toast.success(doc?.duplicate ? "This scan is already in your vault" : "Saved as a PDF");
      router.push(doc?.id ? `/documents/${doc.id}` : "/documents");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not save this scan");
      setBusy(false);
    }
  }

  return (
    <div className="relative flex h-dvh flex-col bg-black text-white">
      <header className="absolute inset-x-0 top-0 z-20 flex items-center justify-between px-3 pt-[max(0.6rem,env(safe-area-inset-top))]">
        <button type="button" aria-label="Close" className="flex size-11 items-center justify-center rounded-full bg-black/50" onClick={close}>
          <X className="size-5" />
        </button>
        <p className="text-sm font-medium">
          {step === "crop" ? "Crop the page" : step === "save" ? "Save PDF" : "Scan a page"}
        </p>
        {step === "camera" ? (
          <button
            type="button"
            aria-label="Switch camera"
            className="flex size-11 items-center justify-center rounded-full bg-black/50"
            onClick={() => setFacing((current) => (current === "environment" ? "user" : "environment"))}
          >
            <SwitchCamera className="size-5" />
          </button>
        ) : (
          <span className="size-11" />
        )}
      </header>

      {step === "camera" && (
        <>
          <video ref={videoRef} playsInline muted autoPlay className="h-full w-full object-cover" />
          {!live && (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 px-8 text-center">
              <Camera className="size-10 text-white/80" />
              <p className="text-sm text-white/80">Allow the camera, or take a photo of the page.</p>
              <Button type="button" className="rounded-full" onClick={() => fileRef.current?.click()}>
                Take photo
              </Button>
            </div>
          )}
          <div className="absolute inset-x-0 bottom-0 z-20 flex flex-col items-center gap-4 bg-gradient-to-t from-black/80 to-transparent px-4 pb-[max(1.25rem,env(safe-area-inset-bottom))] pt-16">
            {pages.length > 0 && (
              <div className="flex w-full gap-2 overflow-x-auto">
                {pages.map((page, index) => (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img key={page.preview} src={page.preview} alt={`Page ${index + 1}`} className="h-16 w-12 shrink-0 rounded-md object-cover" />
                ))}
              </div>
            )}
            <div className="flex w-full items-center justify-between gap-3">
              <button type="button" className="text-sm text-white/80" onClick={() => fileRef.current?.click()}>
                Photos
              </button>
              <button
                type="button"
                aria-label="Capture"
                className="flex size-[4.5rem] items-center justify-center rounded-full border-4 border-white bg-white/15"
                onClick={() => void captureFrame()}
              >
                <span className="size-14 rounded-full bg-white" />
              </button>
              {pages.length > 0 ? (
                <button type="button" className="text-sm font-medium" onClick={() => setStep("save")}>
                  Next ({pages.length})
                </button>
              ) : (
                <span className="w-12" />
              )}
            </div>
          </div>
        </>
      )}

      {step === "crop" && shot && (
        <>
          <div className="min-h-0 flex-1 pt-16 pb-28">
            <PageCropper src={shot} onChange={onCrop} />
          </div>
          <div className="absolute inset-x-0 bottom-0 z-20 flex gap-3 px-4 pb-[max(1.25rem,env(safe-area-inset-bottom))]">
            <Button type="button" variant="outline" className="flex-1 rounded-full border-white/20 bg-black/40 text-white" onClick={() => setStep("camera")}>
              Retake
            </Button>
            <Button type="button" className="flex-1 rounded-full" disabled={busy} onClick={() => void keepPage()}>
              {busy ? "Cropping…" : "Keep page"}
            </Button>
          </div>
        </>
      )}

      {step === "save" && (
        <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto px-4 pt-20 pb-[max(1.5rem,env(safe-area-inset-bottom))]">
          <div className="flex gap-2 overflow-x-auto">
            {pages.map((page, index) => (
              // eslint-disable-next-line @next/next/no-img-element
              <img key={page.preview} src={page.preview} alt={`Page ${index + 1}`} className="h-28 w-20 shrink-0 rounded-xl object-cover" />
            ))}
            {pages.length < SCAN_MAX_PAGES && (
              <button
                type="button"
                className="flex h-28 w-20 shrink-0 flex-col items-center justify-center gap-1 rounded-xl border border-dashed border-white/30 text-xs"
                onClick={() => setStep("camera")}
              >
                <Plus className="size-5" />
                Add page
              </button>
            )}
          </div>
          <label className="block space-y-1.5">
            <span className="text-sm text-white/70">Name</span>
            <Input value={title} onChange={(event) => setTitle(event.target.value)} className="h-11 rounded-xl bg-white/10 text-white" />
          </label>
          {collections.length > 0 && (
            <label className="block space-y-1.5">
              <span className="text-sm text-white/70">Collection</span>
              <select
                value={targetId}
                onChange={(event) => setTargetId(event.target.value)}
                className="h-11 w-full rounded-xl border border-white/20 bg-white/10 px-3 text-sm"
              >
                {collections.map((col) => (
                  <option key={col.id} value={col.id}>
                    {col.name?.trim() || "Untitled"}
                    {col.is_default ? " (Default)" : ""}
                  </option>
                ))}
              </select>
            </label>
          )}
          <Button size="xl" className="mt-auto rounded-full" disabled={busy || !title.trim()} onClick={() => void savePdf()}>
            <Check className="size-4" />
            {busy ? "Saving…" : `Save ${pages.length} page PDF`}
          </Button>
        </div>
      )}

      <input
        ref={fileRef}
        type="file"
        accept="image/*"
        capture="environment"
        className="hidden"
        onChange={(event) => {
          onPicked(event.target.files?.[0]);
          event.target.value = "";
        }}
      />
    </div>
  );
}
