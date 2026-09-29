"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useDropzone } from "react-dropzone";
import { toast } from "sonner";
import { Camera, FolderDown, X } from "lucide-react";
import { api, apiFormWithProgress, apiNdjson } from "@/lib/api";
import { VAULT_FILE_ACCEPT } from "@/lib/file-accept";
import { takeSharedFiles } from "@/lib/share-target";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Progress, ProgressLabel, ProgressValue } from "@/components/ui/progress";

type Collection = {
  id: string;
  name: string;
  parent_id?: string | null;
  is_default?: boolean;
  shared?: boolean;
};

type Uploaded = {
  id: string;
  title?: string;
  duplicate?: boolean;
};

function fileStem(name: string) {
  return name.replace(/\.[^.]+$/, "") || name;
}

export default function UploadPage() {
  return (
    <Suspense fallback={<p className="text-sm text-muted-foreground">Loading…</p>}>
      <UploadForm />
    </Suspense>
  );
}

function UploadForm() {
  const router = useRouter();
  const queryCollection = useSearchParams().get("collection") || "";
  const [files, setFiles] = useState<File[]>([]);
  const [titles, setTitles] = useState<string[]>([]);
  const [collections, setCollections] = useState<Collection[]>([]);
  const [targetId, setTargetId] = useState(queryCollection);
  const [busy, setBusy] = useState(false);
  const [driveUrl, setDriveUrl] = useState("");
  const [driveBusy, setDriveBusy] = useState(false);
  const [uploadPercent, setUploadPercent] = useState(0);
  const [uploadLabel, setUploadLabel] = useState("");
  const [drivePercent, setDrivePercent] = useState(0);
  const [driveLabel, setDriveLabel] = useState("");

  const collectionName = collections.find((col) => col.id === targetId)?.name?.trim() || "";

  useEffect(() => {
    api<Collection[]>("/collections")
      .then((cols) => {
        const owned = cols.filter((col) => !col.shared);
        setCollections(owned);
        setTargetId((current) => {
          if (current && owned.some((col) => col.id === current)) return current;
          const fallback = owned.find((col) => col.is_default) || owned[0];
          return fallback?.id || "";
        });
      })
      .catch(() => undefined);
  }, []);

  const addFiles = useCallback((incoming: File[]) => {
    if (!incoming.length) return;
    setFiles((current) => {
      const names = new Set(current.map((file) => `${file.name}-${file.size}`));
      const extra = incoming.filter((file) => !names.has(`${file.name}-${file.size}`));
      if (!extra.length) return current;
      setTitles((currentTitles) => [...currentTitles, ...extra.map((file) => fileStem(file.name))]);
      return [...current, ...extra];
    });
  }, []);

  useEffect(() => {
    let alive = true;
    takeSharedFiles().then((incoming) => {
      if (!alive || !incoming.length) return;
      addFiles(incoming);
      toast.success(incoming.length === 1 ? "Ready to save this shared file" : `Ready to save ${incoming.length} shared files`);
    });
    return () => {
      alive = false;
    };
  }, [addFiles]);

  const { getRootProps, getInputProps, isDragActive, open } = useDropzone({
    onDrop: addFiles,
    noClick: true,
    multiple: true,
  });

  async function upload() {
    if (!files.length) return;
    if (titles.some((title) => !title.trim())) {
      toast.error("Give each file a name");
      return;
    }
    setBusy(true);
    setUploadPercent(0);
    setUploadLabel("Starting…");
    try {
      const uploaded: Uploaded[] = [];
      const weight = 100 / files.length;
      for (let index = 0; index < files.length; index += 1) {
        setUploadLabel(`Uploading ${index + 1} of ${files.length}`);
        const body = new FormData();
        body.append("files", files[index]);
        body.append("title", titles[index].trim());
        if (targetId) body.append("collection_id", targetId);
        const result = await apiFormWithProgress<{ documents: Uploaded[] }>(
          "/documents/upload",
          body,
          (filePercent) => {
            setUploadPercent(Math.round(index * weight + (filePercent / 100) * weight));
          },
        );
        uploaded.push(...(result.documents || []));
        setUploadPercent(Math.round((index + 1) * weight));
      }
      const dupes = uploaded.filter((doc) => doc.duplicate).length;
      toast.success(
        dupes
          ? `Uploaded. ${dupes} already in vault.`
          : collectionName
            ? `Saved to ${collectionName}`
            : "Saved to Default",
      );
      router.push(targetId ? `/collections?folder=${encodeURIComponent(targetId)}` : "/documents");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Upload failed");
      setBusy(false);
    }
  }

  async function importDriveFolder() {
    const url = driveUrl.trim();
    if (!url) {
      toast.error("Paste a Google Drive folder link");
      return;
    }
    setDriveBusy(true);
    setDrivePercent(3);
    setDriveLabel("Finding files…");
    try {
      const result = await apiNdjson("/documents/import-drive?stream=true", {
        url,
        collection_id: targetId || undefined,
      }, (event) => {
        if (event.type === "start") {
          setDrivePercent(Number(event.percent) || 5);
          setDriveLabel("Finding files…");
          return;
        }
        if (event.type === "progress") {
          setDrivePercent(Number(event.percent) || 0);
          const name = String(event.name || "").trim();
          const done = Number(event.done) || 0;
          const total = Number(event.total) || 0;
          setDriveLabel(
            total
              ? `Saving ${done} of ${total}${name ? ` · ${name}` : ""}`
              : name || "Importing…",
          );
        }
      });
      const documents = (result.documents || []) as Uploaded[];
      const skippedList = (result.skipped || []) as { name: string; reason: string }[];
      const imported = documents.length;
      const skipped = skippedList.length;
      const names = documents
        .map((doc) => doc.title?.trim())
        .filter(Boolean)
        .slice(0, 4)
        .join(", ");
      toast.success(
        skipped
          ? `Saved ${imported} file${imported === 1 ? "" : "s"}${names ? `: ${names}` : ""}. Skipped ${skipped}.`
          : names
            ? `Saved to vault: ${names}`
            : collectionName
              ? `Imported to ${collectionName}`
              : "Imported from Google Drive",
      );
      router.push(targetId ? `/collections?folder=${encodeURIComponent(targetId)}` : "/documents");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Drive import failed");
      setDriveBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-3xl">Add files</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {collectionName ? `Saves to ${collectionName}` : "Saves to Default"}. Scan a page, choose files, or import a Google Drive folder.
          </p>
        </div>
        <div className="flex shrink-0 gap-2">
          <Button type="button" variant="outline" className="rounded-full" onClick={() => router.push("/documents/scan")}>
            <Camera className="size-4" />
            Scan
          </Button>
          <Button type="button" className="rounded-full" onClick={open}>
            Choose
          </Button>
        </div>
      </div>

      {collections.length > 0 && (
        <label className="block space-y-1.5">
          <span className="text-sm font-medium">Collection</span>
          <select
            value={targetId}
            onChange={(event) => setTargetId(event.target.value)}
            className="h-11 w-full rounded-xl border border-input bg-background px-3 text-sm"
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

      <div className="space-y-3 rounded-2xl border bg-card p-4">
        <div className="flex items-center gap-2">
          <FolderDown className="size-4 text-muted-foreground" />
          <p className="text-sm font-medium">Google Drive folder</p>
        </div>
        <p className="text-sm text-muted-foreground">
          Paste a public folder link, then click Import. Anyone-with-the-link folders do not need Google permission. Up to 400 files go into the collection above — they will not appear in the drop box below.
        </p>
        <Input
          value={driveUrl}
          onChange={(event) => setDriveUrl(event.target.value)}
          placeholder="https://drive.google.com/drive/folders/…"
          inputMode="url"
          autoComplete="off"
          disabled={driveBusy}
        />
        <Button
          type="button"
          variant="outline"
          className="rounded-full"
          disabled={driveBusy || busy}
          onClick={() => void importDriveFolder()}
        >
          {driveBusy ? `${Math.max(drivePercent, 1)}%` : "Import files from folder"}
        </Button>
        {driveBusy && (
          <Progress value={drivePercent} className="w-full items-center">
            <ProgressLabel className="min-w-0 truncate text-xs">{driveLabel || "Importing…"}</ProgressLabel>
            <ProgressValue />
          </Progress>
        )}
      </div>

      <div
        {...getRootProps()}
        className={`rounded-2xl border bg-card p-4 ${isDragActive ? "border-primary" : ""}`}
      >
        <input {...getInputProps()} accept={VAULT_FILE_ACCEPT} />
        {files.length === 0 ? (
          <button type="button" className="w-full py-10 text-sm text-muted-foreground" onClick={open}>
            {isDragActive ? "Drop files" : "Drop photos, PDFs, or Word files"}
          </button>
        ) : (
          <div className="space-y-3">
            {files.map((file, index) => (
              <div key={`${file.name}-${index}`} className="rounded-2xl bg-muted/40 px-3 py-2">
                <div className="flex items-center gap-3">
                  <p className="min-w-0 flex-1 truncate text-xs text-muted-foreground">{file.name}</p>
                  <button
                    type="button"
                    className="rounded-full p-1 text-muted-foreground hover:bg-muted"
                    onClick={() => {
                      setFiles((current) => current.filter((_, i) => i !== index));
                      setTitles((current) => current.filter((_, i) => i !== index));
                    }}
                    aria-label={`Remove ${file.name}`}
                  >
                    <X className="size-4" />
                  </button>
                </div>
                <Input
                  className="mt-2"
                  value={titles[index] || ""}
                  placeholder="File name"
                  onChange={(e) =>
                    setTitles((current) => current.map((title, i) => (i === index ? e.target.value : title)))
                  }
                />
              </div>
            ))}
          </div>
        )}
      </div>

      {files.length > 0 && (
        <div className="space-y-3">
          {busy && (
            <Progress value={uploadPercent} className="w-full items-center">
              <ProgressLabel className="min-w-0 truncate text-xs">{uploadLabel || "Uploading…"}</ProgressLabel>
              <ProgressValue />
            </Progress>
          )}
          <Button size="xl" className="rounded-full" disabled={busy || titles.some((title) => !title.trim())} onClick={upload}>
            {busy ? `${Math.max(uploadPercent, 1)}%` : "Upload"}
          </Button>
        </div>
      )}
    </div>
  );
}
