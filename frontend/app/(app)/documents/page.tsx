"use client";

import { Suspense, useEffect, useMemo, useState, type ReactNode } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { FolderOpen, Upload } from "lucide-react";
import { api } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { DocumentThumb } from "@/components/document-thumb";
import { FileActions } from "@/components/file-actions";
import { fileKind, storedKind, type StoredKind } from "@/lib/file-kind";
import { fileTimestamps } from "@/lib/file-time";

type Doc = {
  id: string;
  title: string;
  status: string;
  sensitivity: string;
  expiry_date?: string | null;
  ai_classification?: string | null;
  original_filename: string;
  mime_type?: string;
  download_count?: number;
  share_count?: number;
  use_count?: number;
  created_at?: string;
  updated_at?: string;
};

const KIND_COPY: Record<StoredKind, { title: string; hint: string; empty: string }> = {
  photo: {
    title: "Photos",
    hint: "Images in your vault",
    empty: "No photos in your vault yet.",
  },
  pdf: {
    title: "PDFs",
    hint: "PDF files in your vault",
    empty: "No PDFs in your vault yet.",
  },
  other: {
    title: "Other files",
    hint: "Word, spreadsheets, and everything else",
    empty: "No other files in your vault yet.",
  },
};

function parseKind(value: string | null): StoredKind | null {
  if (value === "photo" || value === "pdf" || value === "other") return value;
  return null;
}

function useCount(doc: Doc) {
  return doc.use_count ?? (doc.download_count || 0) + (doc.share_count || 0);
}

function DocRow({ doc }: { doc: Doc }) {
  const kind = fileKind(doc);
  const uses = useCount(doc);
  const when = fileTimestamps(doc.created_at, doc.updated_at);
  return (
    <div className="flex items-center gap-3 rounded-2xl border border-transparent bg-card px-3 py-2.5 shadow-sm transition hover:border-border">
      <Link href={`/documents/${doc.id}`} className="flex min-w-0 flex-1 items-center gap-3">
        <span className="relative size-14 shrink-0 overflow-hidden rounded-2xl bg-muted">
          <DocumentThumb
            id={doc.id}
            title={doc.title}
            mimeType={doc.mime_type}
            filename={doc.original_filename}
            className="size-full"
          />
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex items-center gap-2">
            <span className="truncate font-medium">{doc.title}</span>
            {uses > 0 && (
              <Badge variant="secondary" className="shrink-0 font-mono text-[10px]">
                {uses}× used
              </Badge>
            )}
          </span>
          <span className="mt-0.5 block truncate text-xs text-muted-foreground">
            {kind.label}
            {doc.ai_classification ? ` · ${doc.ai_classification}` : ""}
            {doc.expiry_date ? ` · expires ${doc.expiry_date}` : ""}
          </span>
          {when ? <span className="mt-0.5 block truncate text-xs text-muted-foreground">{when}</span> : null}
        </span>
      </Link>
      <FileActions id={doc.id} title={doc.title} filename={doc.original_filename} />
    </div>
  );
}

function Section({ title, count, children }: { title: string; count: number; children: ReactNode }) {
  return (
    <section className="space-y-2">
      <div className="flex items-center justify-between px-1">
        <h2 className="text-sm font-semibold tracking-tight text-muted-foreground">{title}</h2>
        <span className="font-mono text-[11px] text-muted-foreground">{count}</span>
      </div>
      <div className="space-y-2">{children}</div>
    </section>
  );
}

export default function DocumentsPage() {
  return (
    <Suspense fallback={<p className="mx-auto max-w-3xl text-sm text-muted-foreground">Loading files…</p>}>
      <DocumentsBrowser />
    </Suspense>
  );
}

function DocumentsBrowser() {
  const searchParams = useSearchParams();
  const kind = parseKind(searchParams.get("kind"));
  const [items, setItems] = useState<Doc[]>([]);
  const copy = kind ? KIND_COPY[kind] : null;

  useEffect(() => {
    api<{ items: Doc[] }>("/documents?limit=200").then((d) => setItems(d.items));
  }, []);

  const visible = useMemo(
    () => (kind ? items.filter((doc) => storedKind(doc) === kind) : items),
    [items, kind],
  );
  const frequent = useMemo(() => (kind ? [] : visible.filter((doc) => useCount(doc) > 0)), [kind, visible]);
  const rest = useMemo(() => visible.filter((doc) => useCount(doc) === 0), [visible]);

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div className="flex items-end justify-between gap-3">
        <div>
          <h1 className="text-3xl">{copy?.title || "Documents"}</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {copy?.hint || "Everything in your vault, with the files you download or share most at the top."}
          </p>
          {kind ? (
            <Link href="/documents" className="mt-1 inline-block text-xs text-muted-foreground hover:text-foreground">
              All files
            </Link>
          ) : (
            <Link href="/trash" className="mt-1 inline-block text-xs text-muted-foreground hover:text-foreground">
              Open trash
            </Link>
          )}
        </div>
        <Link
          href="/documents/upload"
          className="inline-flex shrink-0 items-center gap-2 rounded-full bg-primary px-4 py-2 text-sm text-primary-foreground"
        >
          <Upload className="size-4" />
          Upload
        </Link>
      </div>
      {visible.length === 0 ? (
        <div className="rounded-2xl border bg-card px-6 py-12 text-center">
          <div className="mx-auto mb-4 flex size-14 items-center justify-center rounded-2xl bg-accent">
            <FolderOpen className="size-6 text-accent-foreground" />
          </div>
          <p className="font-medium">{items.length === 0 ? "No files yet" : copy?.empty || "No files yet"}</p>
          <p className="mt-1 text-sm text-muted-foreground">
            {items.length === 0
              ? "Upload a file to your vault, or save one from AI into a collection."
              : "Try another category, or upload a file of this type."}
          </p>
          <div className="mt-5 flex justify-center gap-2">
            <Link href="/documents/upload" className="inline-flex items-center gap-2 rounded-full bg-primary px-4 py-2 text-sm text-primary-foreground">
              <Upload className="size-4" />
              Upload a file
            </Link>
            {kind ? (
              <Link href="/documents" className="rounded-full border px-4 py-2 text-sm">
                All files
              </Link>
            ) : (
              <Link href="/collections" className="rounded-full border px-4 py-2 text-sm">
                Open collections
              </Link>
            )}
          </div>
        </div>
      ) : (
        <div className="space-y-7">
          {frequent.length > 0 && (
            <Section title="Frequently used" count={frequent.length}>
              {frequent.map((doc) => (
                <DocRow key={doc.id} doc={doc} />
              ))}
            </Section>
          )}
          {(frequent.length ? rest : visible).length > 0 && (
            <Section title={kind ? copy?.title || "Files" : frequent.length ? "All files" : "Your files"} count={(frequent.length ? rest : visible).length}>
              {(frequent.length ? rest : visible).map((doc) => (
                <DocRow key={doc.id} doc={doc} />
              ))}
            </Section>
          )}
        </div>
      )}
      <Link
        href="/documents/upload"
        aria-label="Upload a file"
        className="fixed right-4 z-20 flex size-14 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg md:hidden"
        style={{ bottom: "calc(4.75rem + env(safe-area-inset-bottom))" }}
      >
        <Upload className="size-6" />
      </Link>
    </div>
  );
}