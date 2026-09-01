"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useDropzone } from "react-dropzone";
import { toast } from "sonner";
import { X } from "lucide-react";
import { api, apiForm } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type Collection = {
  id: string;
  name: string;
  parent_id?: string | null;
};

type Uploaded = {
  id: string;
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
  const collectionId = useSearchParams().get("collection") || "";
  const [files, setFiles] = useState<File[]>([]);
  const [titles, setTitles] = useState<string[]>([]);
  const [collectionName, setCollectionName] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!collectionId) return;
    api<Collection[]>("/collections")
      .then((cols) => {
        const col = cols.find((item) => item.id === collectionId);
        setCollectionName(col?.name?.trim() || "");
      })
      .catch(() => undefined);
  }, [collectionId]);

  const addFiles = useCallback((incoming: File[]) => {
    setFiles((current) => {
      const names = new Set(current.map((file) => `${file.name}-${file.size}`));
      return [...current, ...incoming.filter((file) => !names.has(`${file.name}-${file.size}`))];
    });
    setTitles((current) => {
      const existing = files.map((file) => `${file.name}-${file.size}`);
      const names = new Set(existing);
      const extra = incoming.filter((file) => !names.has(`${file.name}-${file.size}`));
      return [...current, ...extra.map((file) => fileStem(file.name))];
    });
  }, [files]);

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
    try {
      const uploaded: Uploaded[] = [];
      for (let index = 0; index < files.length; index += 1) {
        const body = new FormData();
        body.append("files", files[index]);
        body.append("title", titles[index].trim());
        if (collectionId) body.append("collection_id", collectionId);
        const result = await apiForm<{ documents: Uploaded[] }>("/documents/upload", body);
        uploaded.push(...(result.documents || []));
      }
      const dupes = uploaded.filter((doc) => doc.duplicate).length;
      toast.success(
        dupes
          ? `Uploaded. ${dupes} already in vault.`
          : collectionName
            ? `Saved to ${collectionName}`
            : "Saved to Default",
      );
      router.push(collectionId ? "/collections" : "/documents");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Upload failed");
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-3xl">Add files</h1>
          {collectionName ? (
            <p className="mt-1 text-sm text-muted-foreground">{collectionName}</p>
          ) : (
            <p className="mt-1 text-sm text-muted-foreground">Saves to Default</p>
          )}
        </div>
        <Button type="button" className="rounded-full" onClick={open}>
          Choose
        </Button>
      </div>

      <div
        {...getRootProps()}
        className={`rounded-2xl border bg-card p-4 ${isDragActive ? "border-primary" : ""}`}
      >
        <input {...getInputProps()} />
        {files.length === 0 ? (
          <button type="button" className="w-full py-10 text-sm text-muted-foreground" onClick={open}>
            {isDragActive ? "Drop files" : "Drop files here or choose"}
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
        <Button size="xl" className="rounded-full" disabled={busy || titles.some((title) => !title.trim())} onClick={upload}>
          {busy ? "Uploading…" : "Upload"}
        </Button>
      )}
    </div>
  );
}
