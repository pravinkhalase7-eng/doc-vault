"use client";

import { useEffect, useState } from "react";
import { Check, Folder, FolderPlus } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";

export type VaultCollection = {
  id: string;
  name: string;
  document_ids?: string[];
  is_default?: boolean;
};

export async function moveDocumentToCollection(documentId: string, collectionId: string) {
  await api(`/documents/${documentId}/move`, {
    method: "POST",
    body: JSON.stringify({ collection_id: collectionId }),
  });
}

export function MoveCollectionSheet({
  documentId,
  currentIds,
  open,
  onOpenChange,
  onMoved,
}: {
  documentId: string;
  currentIds?: string[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onMoved?: () => void | Promise<void>;
}) {
  const [collections, setCollections] = useState<VaultCollection[]>([]);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!open) {
      setLoaded(false);
      setCollections([]);
      return;
    }
    api<VaultCollection[]>("/collections")
      .then((cols) => {
        setCollections(cols);
        setLoaded(true);
      })
      .catch((err) => toast.error(err instanceof Error ? err.message : "Could not load collections"));
  }, [open]);

  async function moveTo(col: VaultCollection) {
    if (!documentId || busy) return;
    if (currentIds?.includes(col.id)) {
      onOpenChange(false);
      return;
    }
    setBusy(true);
    try {
      await moveDocumentToCollection(documentId, col.id);
      toast.success(`Moved to ${col.name || "Untitled"}`);
      onOpenChange(false);
      await onMoved?.();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not move file");
    } finally {
      setBusy(false);
    }
  }

  async function createAndMove() {
    const trimmed = name.trim();
    if (!trimmed || !documentId) return;
    setBusy(true);
    try {
      const created = await api<VaultCollection>("/collections", {
        method: "POST",
        body: JSON.stringify({ name: trimmed }),
      });
      setName("");
      await moveDocumentToCollection(documentId, created.id);
      toast.success(`Moved to ${created.name}`);
      onOpenChange(false);
      await onMoved?.();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not create collection");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="bottom" className="h-[min(80dvh,36rem)] rounded-t-3xl" finalFocus={false}>
        <SheetHeader>
          <SheetTitle>Move to collection</SheetTitle>
        </SheetHeader>
        <div className="flex min-h-0 flex-1 flex-col gap-3 px-4 pb-4">
          <div className="min-h-0 flex-1 space-y-1 overflow-y-auto">
            {!loaded && (
              <p className="py-6 text-center text-sm text-muted-foreground">Loading…</p>
            )}
            {loaded && collections.length === 0 && (
              <p className="py-6 text-center text-sm text-muted-foreground">
                No collections yet. Create one below.
              </p>
            )}
            {collections.map((col) => {
              const current = currentIds?.includes(col.id);
              return (
                <button
                  key={col.id}
                  type="button"
                  disabled={busy}
                  onClick={() => void moveTo(col)}
                  className="flex w-full items-center gap-3 rounded-2xl px-3 py-2 text-left hover:bg-muted disabled:opacity-60"
                >
                  <span className="flex size-10 items-center justify-center rounded-xl bg-accent text-accent-foreground">
                    <Folder className="size-4" />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium">{col.name || "Untitled"}</span>
                    <span className="block text-xs text-muted-foreground">
                      {current ? "Current collection" : `${col.document_ids?.length || 0} files`}
                    </span>
                  </span>
                  {current && <Check className="size-4 text-primary" />}
                </button>
              );
            })}
          </div>
          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              void createAndMove();
            }}
          >
            <Input
              placeholder="New collection name"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
            <Button type="submit" className="rounded-full" disabled={busy || !name.trim()}>
              <FolderPlus className="size-4" />
              Create
            </Button>
          </form>
        </div>
      </SheetContent>
    </Sheet>
  );
}
