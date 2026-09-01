"use client";

import { useState } from "react";
import { Download, FolderInput, Share2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { MoveCollectionSheet } from "@/components/move-collection-sheet";
import { downloadDocument, isShareCancel, shareDocument } from "@/lib/files";
import { cn } from "@/lib/utils";

export function FileActions({
  id,
  title,
  filename,
  currentCollectionId,
  onMoved,
  className,
}: {
  id: string;
  title: string;
  filename: string;
  currentCollectionId?: string;
  onMoved?: () => void | Promise<void>;
  className?: string;
}) {
  const [moveOpen, setMoveOpen] = useState(false);

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

  return (
    <div className={cn("flex shrink-0 items-center gap-1", className)}>
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
      <MoveCollectionSheet
        documentId={id}
        currentIds={currentCollectionId ? [currentCollectionId] : undefined}
        open={moveOpen}
        onOpenChange={setMoveOpen}
        onMoved={onMoved}
      />
    </div>
  );
}
