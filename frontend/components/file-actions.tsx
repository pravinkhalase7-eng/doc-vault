"use client";

import { useState } from "react";
import { Download, FolderInput, Share2, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { MoveCollectionSheet } from "@/components/move-collection-sheet";
import { api } from "@/lib/api";
import { downloadDocument, isShareCancel, shareDocument } from "@/lib/files";
import { cn } from "@/lib/utils";
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

export function FileActions({
  id,
  title,
  filename,
  currentCollectionId,
  onMoved,
  onDeleted,
  className,
}: {
  id: string;
  title: string;
  filename: string;
  currentCollectionId?: string;
  onMoved?: () => void | Promise<void>;
  onDeleted?: () => void | Promise<void>;
  className?: string;
}) {
  const [moveOpen, setMoveOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);

  async function onShare() {
    try {
      await shareDocument(id, title, filename);
    } catch (err) {
      if (isShareCancel(err)) return;
      toast.error(err instanceof Error ? err.message : "Could not share");
    }
  }

  async function onDownload() {
    try {
      await downloadDocument(id, filename);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Download failed");
    }
  }

  async function confirmDelete() {
    if (deleting) return;
    setDeleting(true);
    try {
      await api(`/documents/${id}`, { method: "DELETE" });
      toast.success("Moved to trash");
      setDeleteOpen(false);
      await onDeleted?.();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not delete");
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div className={cn("flex shrink-0 items-center gap-1.5", className)}>
      <Button type="button" variant="ghost" size="icon-sm" className="rounded-full" onClick={() => setMoveOpen(true)}>
        <FolderInput className="size-4" />
        <span className="sr-only">Move</span>
      </Button>
      <Button type="button" variant="ghost" size="icon-sm" className="rounded-full" onClick={onShare}>
        <Share2 className="size-4" />
        <span className="sr-only">Share</span>
      </Button>
      <Button type="button" variant="ghost" size="icon-sm" className="rounded-full" onClick={onDownload}>
        <Download className="size-4" />
        <span className="sr-only">Download</span>
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="icon-sm"
        className="rounded-full text-destructive hover:text-destructive"
        onClick={() => setDeleteOpen(true)}
      >
        <Trash2 className="size-4" />
        <span className="sr-only">Move to trash</span>
      </Button>
      <MoveCollectionSheet
        documentId={id}
        currentIds={currentCollectionId ? [currentCollectionId] : undefined}
        open={moveOpen}
        onOpenChange={setMoveOpen}
        onMoved={onMoved}
      />
      <AlertDialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Move {title} to trash?</AlertDialogTitle>
            <AlertDialogDescription>This deletes the file from your vault (recoverable for 30 days). It is not the same as removing it from a folder.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction variant="destructive" disabled={deleting} onClick={() => void confirmDelete()}>
              {deleting ? "Moving…" : "Move to trash"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
