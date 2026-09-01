"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  Check,
  Download,
  Folder,
  Info,
  MessageSquare,
  Pencil,
  Share2,
} from "lucide-react";
import { api, apiBlob } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { toast } from "sonner";
import { downloadDocument, isShareCancel, shareDocument } from "@/lib/files";
import { MoveCollectionSheet } from "@/components/move-collection-sheet";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";

type Field = {
  id: string;
  field_name: string;
  value: string | null;
  confidence: number | null;
  page: number | null;
  verification_status: string;
};

type CollectionRef = { id: string; name: string };

type Doc = {
  id: string;
  title: string;
  status: string;
  mime_type: string;
  original_filename: string;
  page_count: number | null;
  exclude_from_ai: boolean;
  metadata_fields: Field[];
  sensitivity: string;
  ai_classification?: string | null;
  expiry_date?: string | null;
  collections?: CollectionRef[];
};

const PROCESSING = new Set(["UPLOADING", "UPLOADED", "PROCESSING", "OCR_PROCESSING", "AI_PROCESSING"]);

function goBack(router: ReturnType<typeof useRouter>, fallback = "/documents") {
  const last = typeof window !== "undefined" ? sessionStorage.getItem("dv_return") : null;
  if (last && !last.startsWith("/documents/")) {
    router.push(last);
    return;
  }
  router.push(fallback);
}

export default function DocumentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [doc, setDoc] = useState<Doc | null>(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [folderOpen, setFolderOpen] = useState(false);
  const [titleDraft, setTitleDraft] = useState("");
  const [renaming, setRenaming] = useState(false);
  const [zoom, setZoom] = useState(1);

  async function load() {
    const data = await api<Doc>(`/documents/${id}`);
    setDoc(data);
    setTitleDraft(data.title);
  }

  useEffect(() => {
    load().catch((err) => toast.error(err instanceof Error ? err.message : "Could not load file"));
  }, [id]);

  useEffect(() => {
    if (!doc || !PROCESSING.has(doc.status)) return;
    const timer = setInterval(() => {
      load().catch(() => undefined);
    }, 2500);
    return () => clearInterval(timer);
  }, [id, doc?.status]);

  useEffect(() => {
    if (!id) return;
    let objectUrl = "";
    let cancelled = false;
    setZoom(1);
    (async () => {
      try {
        const blob = await apiBlob(`/documents/${id}/preview`);
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setPreviewUrl(objectUrl);
      } catch (err) {
        if (!cancelled) toast.error(err instanceof Error ? err.message : "Could not load preview");
      }
    })();
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [id]);

  async function saveTitle() {
    if (!doc) return;
    const title = titleDraft.trim();
    if (!title || title === doc.title) {
      setRenaming(false);
      setTitleDraft(doc.title);
      return;
    }
    try {
      await api(`/documents/${doc.id}`, {
        method: "PATCH",
        body: JSON.stringify({ title }),
      });
      setRenaming(false);
      await load();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not rename");
    }
  }

  async function onShare() {
    if (!doc) return;
    try {
      await shareDocument(doc.id, doc.title, doc.original_filename);
    } catch (err) {
      if (isShareCancel(err)) return;
      toast.error(err instanceof Error ? err.message : "Could not share");
    }
  }

  async function onDownload() {
    if (!doc) return;
    try {
      await downloadDocument(doc.id, doc.original_filename);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Download failed");
    }
  }

  if (!doc) {
    return <p className="p-6 text-sm text-muted-foreground">Loading…</p>;
  }

  const isImage = doc.mime_type.startsWith("image/");
  const inCollections = doc.collections || [];
  const meta = [
    doc.ai_classification,
    doc.expiry_date ? `expires ${doc.expiry_date}` : null,
    inCollections.map((col) => col.name).filter(Boolean).join(" · ") || null,
  ].filter(Boolean);

  return (
    <div className="flex h-full min-h-0 flex-col bg-black">
      <div className="flex items-center gap-2 border-b border-white/10 bg-background px-3 py-2">
        <Button
          variant="ghost"
          size="icon-sm"
          className="rounded-full"
          onClick={() => goBack(router)}
        >
          <ArrowLeft className="size-4" />
          <span className="sr-only">Back</span>
        </Button>
        <div className="min-w-0 flex-1">
          {renaming ? (
            <form
              className="flex items-center gap-1"
              onSubmit={(e) => {
                e.preventDefault();
                void saveTitle();
              }}
            >
              <Input
                autoFocus
                value={titleDraft}
                onChange={(e) => setTitleDraft(e.target.value)}
                onBlur={() => void saveTitle()}
                className="h-8"
              />
              <Button type="submit" variant="ghost" size="icon-sm" className="rounded-full">
                <Check className="size-4" />
              </Button>
            </form>
          ) : (
            <button type="button" className="flex max-w-full items-center gap-1.5 text-left" onClick={() => setRenaming(true)}>
              <h1 className="truncate text-base font-medium">{doc.title}</h1>
              <Pencil className="size-3 shrink-0 text-muted-foreground" />
            </button>
          )}
          {meta.length > 0 && (
            <p className="truncate text-[11px] text-muted-foreground">{meta.join(" · ")}</p>
          )}
        </div>
      </div>

      <div className="relative min-h-0 flex-1 overflow-auto">
        {previewUrl ? (
          isImage ? (
            <button
              type="button"
              className="flex h-full min-h-full w-full items-center justify-center"
              onClick={() => setZoom((value) => (value === 1 ? 2 : 1))}
              aria-label={zoom === 1 ? "Zoom in" : "Zoom out"}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={previewUrl}
                alt={doc.title}
                className="max-h-full max-w-full object-contain transition-transform"
                style={{ transform: `scale(${zoom})`, transformOrigin: "center center" }}
              />
            </button>
          ) : (
            <iframe title={doc.title} className="h-full w-full border-0 bg-neutral-900" src={previewUrl} />
          )
        ) : (
          <div className="flex h-full items-center justify-center text-sm text-white/60">Loading preview…</div>
        )}
      </div>

      <div className="grid grid-cols-5 border-t border-white/10 bg-background px-1 pt-2 pb-[max(0.5rem,env(safe-area-inset-bottom))]">
        <Action
          icon={MessageSquare}
          label="Ask AI"
          accent
          onClick={() =>
            router.push(
              `/ai?q=${encodeURIComponent(`What can you tell me about ${doc.title}?`)}&doc=${doc.id}`,
            )
          }
        />
        <Action icon={Folder} label="Move" onClick={() => setFolderOpen(true)} />
        <Action icon={Share2} label="Share" onClick={() => void onShare()} />
        <Action icon={Download} label="Save" onClick={() => void onDownload()} />
        <Action icon={Info} label="Details" onClick={() => setDetailsOpen(true)} />
      </div>

      <MoveCollectionSheet
        documentId={doc.id}
        currentIds={(doc.collections || []).map((col) => col.id)}
        open={folderOpen}
        onOpenChange={setFolderOpen}
        onMoved={load}
      />

      <Sheet open={detailsOpen} onOpenChange={setDetailsOpen}>
        <SheetContent className="p-0" finalFocus={false}>
          <SheetHeader>
            <SheetTitle>Details</SheetTitle>
          </SheetHeader>
          <div className="space-y-5 overflow-y-auto px-4 pb-6">
            <div>
              <p className="text-xs text-muted-foreground">File name</p>
              <p className="break-all text-sm">{doc.original_filename}</p>
            </div>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <p className="text-xs text-muted-foreground">Status</p>
                <p>{doc.status}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Sensitivity</p>
                <p>{doc.sensitivity}</p>
              </div>
            </div>
            {inCollections.length > 0 && (
              <div>
                <p className="mb-2 text-xs text-muted-foreground">Collections</p>
                <div className="flex flex-wrap gap-2">
                  {inCollections.map((col) => (
                    <span key={col.id} className="rounded-full bg-accent px-3 py-1 text-xs text-accent-foreground">
                      {col.name}
                    </span>
                  ))}
                </div>
              </div>
            )}
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="font-medium">Exclude from AI</p>
                <p className="text-xs text-muted-foreground">Skip this file in search and chat.</p>
              </div>
              <Switch
                checked={doc.exclude_from_ai}
                onCheckedChange={async (checked) => {
                  await api(`/documents/${doc.id}`, {
                    method: "PATCH",
                    body: JSON.stringify({ exclude_from_ai: checked }),
                  });
                  toast.success(checked ? "Excluded from AI" : "AI indexing enabled");
                  load();
                }}
              />
            </div>
            <div>
              <p className="mb-2 font-medium">Extracted fields</p>
              {doc.metadata_fields?.length ? (
                <div className="space-y-2">
                  {doc.metadata_fields.map((field) => (
                    <div key={field.id} className="flex justify-between gap-2 rounded-xl bg-muted px-3 py-2 text-sm">
                      <span>{field.field_name}</span>
                      <span className="text-muted-foreground">{field.value || "—"}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">Nothing extracted yet.</p>
              )}
            </div>
            <Button
              variant="destructive"
              className="w-full rounded-full"
              onClick={async () => {
                await api(`/documents/${doc.id}`, { method: "DELETE" });
                goBack(router);
              }}
            >
              Move to trash
            </Button>
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}

function Action({
  icon: Icon,
  label,
  onClick,
  accent,
}: {
  icon: typeof MessageSquare;
  label: string;
  onClick: () => void;
  accent?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex flex-col items-center gap-1 rounded-xl py-1 text-[11px] text-muted-foreground hover:bg-muted"
    >
      <Icon className={accent ? "size-5 text-[var(--mint)]" : "size-5"} />
      {label}
    </button>
  );
}
