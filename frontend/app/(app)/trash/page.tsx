"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Trash2 } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { fileKind } from "@/lib/file-kind";
import { cn } from "@/lib/utils";
import { trashDaysLeft } from "@/lib/expiry";

type Doc = {
  id: string;
  title: string;
  original_filename: string;
  mime_type?: string;
  trashed_at?: string | null;
  ai_classification?: string | null;
};

export default function TrashPage() {
  const [items, setItems] = useState<Doc[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [pending, setPending] = useState<Doc | null>(null);

  async function load() {
    try {
      const data = await api<{ items: Doc[] }>("/documents?trash=true&limit=200");
      setItems(data.items || []);
    } catch {
      toast.error("Could not load trash");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function restore(doc: Doc) {
    setBusyId(doc.id);
    try {
      await api(`/documents/${doc.id}/restore`, { method: "POST" });
      setItems((current) => current.filter((item) => item.id !== doc.id));
      toast.success(`Restored ${doc.title}`);
    } catch {
      toast.error("Could not restore");
    } finally {
      setBusyId(null);
    }
  }

  async function destroy() {
    if (!pending) return;
    setBusyId(pending.id);
    try {
      await api(`/documents/${pending.id}/permanent`, { method: "DELETE" });
      setItems((current) => current.filter((item) => item.id !== pending.id));
      toast.success("Deleted forever");
    } catch {
      toast.error("Could not delete");
    } finally {
      setBusyId(null);
      setPending(null);
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div>
        <h1 className="text-3xl">Trash</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Files stay here for 30 days, then they are removed from the disk.
        </p>
      </div>
      {loading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : items.length === 0 ? (
        <div className="rounded-2xl border bg-card p-8 text-center">
          <Trash2 className="mx-auto mb-3 size-8 text-muted-foreground" />
          <p className="font-medium">Trash is empty</p>
          <p className="mt-1 text-sm text-muted-foreground">Deleted files can be restored from here.</p>
          <Link href="/documents" className="mt-4 inline-block text-sm text-primary">
            Browse files
          </Link>
        </div>
      ) : (
        <div className="space-y-2">
          {items.map((doc) => {
            const kind = fileKind(doc);
            const Icon = kind.icon;
            const days = trashDaysLeft(doc.trashed_at);
            return (
              <div key={doc.id} className="flex items-center gap-3 rounded-2xl border bg-card px-3 py-2.5">
                <Link href={`/documents/${doc.id}`} className="flex min-w-0 flex-1 items-center gap-3">
                  <span className={cn("flex size-11 shrink-0 items-center justify-center rounded-2xl", kind.tone)}>
                    <Icon className="size-4" />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium">{doc.title}</span>
                    <span className="block text-xs text-muted-foreground">
                      {days === 0 ? "Removed soon" : `${days} day${days === 1 ? "" : "s"} left`}
                      {doc.ai_classification ? ` · ${doc.ai_classification}` : ""}
                    </span>
                  </span>
                </Link>
                <Button
                  variant="outline"
                  size="sm"
                  className="rounded-full"
                  disabled={busyId === doc.id}
                  onClick={() => void restore(doc)}
                >
                  Restore
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="rounded-full text-destructive"
                  disabled={busyId === doc.id}
                  onClick={() => setPending(doc)}
                >
                  Delete
                </Button>
              </div>
            );
          })}
        </div>
      )}

      <AlertDialog open={Boolean(pending)} onOpenChange={(open) => !open && setPending(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete {pending?.title || "this file"} forever?</AlertDialogTitle>
            <AlertDialogDescription>
              This removes the original from disk. You cannot undo it.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep in trash</AlertDialogCancel>
            <AlertDialogAction variant="destructive" disabled={Boolean(busyId)} onClick={() => void destroy()}>
              Delete forever
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
